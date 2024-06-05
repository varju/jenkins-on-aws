import os
from configparser import ConfigParser

from aws_cdk import (
    aws_ecs_patterns as ecs_patterns,
    aws_ecs as ecs,
    aws_ecr_assets as ecr,
    aws_ec2 as ec2,
    aws_efs,
    aws_servicediscovery as sd,
    aws_iam as iam,
    Stack,
)
from constructs import Construct

from .codebuild import CodeBuild
from .ecs import ECSCluster
from .jenkins_agent import JenkinsAgent
from .network import Network

config = ConfigParser()
config.read("config.ini")


class JenkinsController(Construct):

    def __init__(
        self,
        scope: Stack,
        ecs_cluster: ECSCluster,
        network: Network,
        agent: JenkinsAgent,
        codebuild: CodeBuild,
    ) -> None:
        super().__init__(scope, "Controller")

        # Building a custom image for jenkins controller.
        self.container_image = ecr.DockerImageAsset(
            self, "DockerImage", directory="./docker/controller/"
        )

        # Task definition details to define the Jenkins controller container
        self.jenkins_task = ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
            family=f"{scope.stack_name}-controller",
            image=ecs.ContainerImage.from_docker_image_asset(self.container_image),
            container_port=8080,
            enable_logging=True,
            environment={
                # https://github.com/jenkinsci/docker/blob/master/README.md#passing-jvm-parameters
                "JAVA_OPTS": " ".join(
                    [
                        "-Djenkins.install.runSetupWizard=false",
                        "-Dhudson.slaves.NodeProvisioner.initialDelay=0",
                        "-Dhudson.slaves.NodeProvisioner.MARGIN=50",
                        "-Dhudson.slaves.NodeProvisioner.MARGIN0=0.85",
                    ]
                ),
                # https://github.com/jenkinsci/configuration-as-code-plugin/blob/master/README.md#getting-started
                "CASC_JENKINS_CONFIG": "/config-as-code.yaml",
                "TZ": "America/Vancouver",
                # Template parameters
                "stack_name": scope.stack_name,
                "cluster_arn": ecs_cluster.cluster.cluster_arn,
                "aws_region": config["DEFAULT"]["region"],
                "jenkins_url": config["DEFAULT"]["jenkins_url"],
                "jenkins_public_url": os.environ["JENKINS_PUBLIC_URL"],
                "subnet_ids": ",".join(
                    [x.subnet_id for x in network.vpc.private_subnets]
                ),
                "security_group_ids": agent.security_group.security_group_id,
                "execution_role_arn": agent.execution_role.role_arn,
                "task_role_arn": agent.task_role.role_arn,
                "agent_log_group": agent.log_group.log_group_name,
                "agent_log_stream_prefix": agent.log_stream.log_stream_name,
                "admin_username": os.environ["ADMIN_USERNAME"],
                "admin_password": os.environ["ADMIN_PASSWORD"],
                "simple_agent_image": agent.simple_agent.container_image.image_uri,
                "postgres12_task_def": agent.postgres12_task_def.task_def.task_definition_arn,
                "agent_image_java_11": agent.java11_agent.container_image.image_uri,
                "gh_credential_id": os.environ["GH_CREDENTIAL_ID"],
                "gh_credential_app_id": os.environ["GH_CREDENTIAL_APP_ID"],
                "gh_credential_private_key": os.environ["GH_CREDENTIAL_PRIVATE_KEY"],
                "gh_credential_owner": os.environ["GH_CREDENTIAL_OWNER"],
                "codebuild_project_name": codebuild.project.project_name,
            },
        )

        # Create the Jenkins controller service
        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "FargateService",
            cpu=int(config["DEFAULT"]["fargate_cpu"]),
            memory_limit_mib=int(config["DEFAULT"]["fargate_memory_limit_mib"]),
            cluster=ecs_cluster.cluster,
            desired_count=1,
            enable_ecs_managed_tags=True,
            task_image_options=self.jenkins_task,
            cloud_map_options=ecs.CloudMapOptions(
                name="controller", dns_record_type=sd.DnsRecordType("A")
            ),
            min_healthy_percent=0,
            max_healthy_percent=100,
        )

        # Reduce time ALB waits when draining tasks; service downtimes will be announced ahead of time
        fargate_service.target_group.set_attribute(
            "deregistration_delay.timeout_seconds", "0"
        )

        controller_service = fargate_service.service
        controller_task = controller_service.task_definition

        # Mount EFS volume
        ecs_cluster.filesystem.connections.allow_default_port_from(controller_service)
        access_point = ecs_cluster.filesystem.add_access_point(
            "AccessPoint",
            path="/jenkins-home",
            posix_user=aws_efs.PosixUser(gid="1000", uid="1000"),
            create_acl=aws_efs.Acl(
                owner_gid="1000", owner_uid="1000", permissions="750"
            ),
        )
        controller_task.add_volume(
            name="jenkins-home",
            efs_volume_configuration=ecs.EfsVolumeConfiguration(
                file_system_id=ecs_cluster.filesystem.file_system_id,
                transit_encryption="ENABLED",
                authorization_config=ecs.AuthorizationConfig(
                    access_point_id=access_point.access_point_id,
                    iam="ENABLED",
                ),
            ),
        )
        controller_task.default_container.add_mount_points(
            ecs.MountPoint(
                container_path="/var/jenkins_home",
                source_volume="jenkins-home",
                read_only=False,
            )
        )

        # Opening port 5000 for controller <--> agent communications
        controller_service.task_definition.default_container.add_port_mappings(
            ecs.PortMapping(container_port=50000, host_port=50000)
        )

        # Enable connection between controller and agents
        for port in [8080, 50000]:
            controller_service.connections.allow_from(
                agent.security_group,
                port_range=ec2.Port(
                    protocol=ec2.Protocol.TCP,
                    string_representation=f"controller to fargate agent {port}",
                    from_port=port,
                    to_port=port,
                ),
            )
            controller_service.connections.allow_from(
                ecs_cluster.asg,
                port_range=ec2.Port(
                    protocol=ec2.Protocol.TCP,
                    string_representation=f"controller to ec2 agent {port}",
                    from_port=port,
                    to_port=port,
                ),
            )

        # IAM Statements to allow jenkins ecs plugin to talk to ECS as well as the Jenkins cluster #
        controller_task.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ecs:RegisterTaskDefinition",
                    "ecs:DeregisterTaskDefinition",
                    "ecs:ListClusters",
                    "ecs:DescribeContainerInstances",
                    "ecs:ListTaskDefinitions",
                    "ecs:DescribeTaskDefinition",
                    "ecs:DescribeTasks",
                    "ecs:TagResource",
                    "ecs:ListTagsForResource",
                ],
                resources=["*"],
            )
        )

        controller_task.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=["ecs:ListContainerInstances"],
                resources=[ecs_cluster.cluster.cluster_arn],
            )
        )

        controller_task.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=["ecs:RunTask"],
                resources=[
                    "arn:aws:ecs:{0}:{1}:task-definition/{2}*".format(
                        scope.region,
                        scope.account,
                        scope.stack_name,
                    )
                ],
            )
        )

        controller_task.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=["ecs:StopTask"],
                resources=[
                    "arn:aws:ecs:{0}:{1}:task/*".format(scope.region, scope.account)
                ],
                conditions={
                    "ForAnyValue:ArnEquals": {
                        "ecs:cluster": ecs_cluster.cluster.cluster_arn
                    }
                },
            )
        )

        controller_task.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[
                    agent.task_role.role_arn,
                    agent.execution_role.role_arn,
                ],
            )
        )

        controller_task.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=[
                    "codebuild:List*",
                    "codebuild:Describe*",
                    "codebuild:Get*",
                    "codebuild:StartBuild",
                    "codebuild:StopBuild",
                    "codebuild:BatchGet*",
                ],
                resources=["*"],
            )
        )
