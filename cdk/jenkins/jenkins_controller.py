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
    ) -> None:
        super().__init__(scope, "Controller")

        # Building a custom image for jenkins controller.
        self.container_image = ecr.DockerImageAsset(
            self, "DockerImage", directory="./docker/controller/"
        )

        # Task definition details to define the Jenkins controller container
        self.jenkins_task = ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
            image=ecs.ContainerImage.from_docker_image_asset(self.container_image),
            container_port=8080,
            enable_logging=True,
            environment={
                # https://github.com/jenkinsci/docker/blob/master/README.md#passing-jvm-parameters
                "JAVA_OPTS": "-Djenkins.install.runSetupWizard=false",
                # https://github.com/jenkinsci/configuration-as-code-plugin/blob/master/README.md#getting-started
                "CASC_JENKINS_CONFIG": "/config-as-code.yaml",
                "stack_name": scope.stack_name,
                "cluster_arn": ecs_cluster.cluster.cluster_arn,
                "aws_region": config["DEFAULT"]["region"],
                "jenkins_url": config["DEFAULT"]["jenkins_url"],
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
                "TZ": "America/Vancouver",
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

        # Enable connection between controller and agent
        controller_service.connections.allow_from(
            agent.security_group,
            port_range=ec2.Port(
                protocol=ec2.Protocol.TCP,
                string_representation="controller to agent 50000",
                from_port=50000,
                to_port=50000,
            ),
        )

        # Enable connection between controller and agent on 8080
        controller_service.connections.allow_from(
            agent.security_group,
            port_range=ec2.Port(
                protocol=ec2.Protocol.TCP,
                string_representation="controller to agent 8080",
                from_port=8080,
                to_port=8080,
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
                        scope.region, scope.account, scope.stack_name,
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
