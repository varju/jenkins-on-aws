import os
from configparser import ConfigParser

from aws_cdk import (
    aws_ecs_patterns as ecs_patterns,
    aws_ecs as ecs,
    aws_ecr_assets as ecr,
    aws_ec2 as ec2,
    aws_servicediscovery as sd,
    aws_iam as iam,
    Stack,
)
from constructs import Construct

config = ConfigParser()
config.read('config.ini')


class JenkinsLeader(Stack):

    def __init__(self, scope: Construct, id: str, cluster, vpc, worker, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        self.cluster = cluster
        self.vpc = vpc
        self.worker = worker

        # Building a custom image for jenkins leader.
        self.container_image = ecr.DockerImageAsset(
            self, "JenkinsleaderDockerImage",
            directory='./docker/leader/'
        )

        # Task definition details to define the Jenkins leader container
        self.jenkins_task = ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
            image=ecs.ContainerImage.from_docker_image_asset(self.container_image),
            container_port=8080,
            enable_logging=True,
            environment={
                # https://github.com/jenkinsci/docker/blob/leader/README.md#passing-jvm-parameters
                'JAVA_OPTS': '-Djenkins.install.runSetupWizard=false',
                # https://github.com/jenkinsci/configuration-as-code-plugin/blob/leader/README.md#getting-started
                'CASC_JENKINS_CONFIG': '/config-as-code.yaml',
                'network_stack': self.vpc.stack_name,
                'cluster_stack': self.cluster.stack_name,
                'worker_stack': self.worker.stack_name,
                'cluster_arn': self.cluster.cluster.cluster_arn,
                'aws_region': config['DEFAULT']['region'],
                'jenkins_url': config['DEFAULT']['jenkins_url'],
                'subnet_ids': ",".join([x.subnet_id for x in self.vpc.vpc.private_subnets]),
                'security_group_ids': self.worker.worker_security_group.security_group_id,
                'execution_role_arn': self.worker.worker_execution_role.role_arn,
                'task_role_arn': self.worker.worker_task_role.role_arn,
                'worker_log_group': self.worker.worker_logs_group.log_group_name,
                'worker_log_stream_prefix': self.worker.worker_log_stream.log_stream_name,
                'admin_username': os.environ['ADMIN_USERNAME'],
                'admin_password': os.environ['ADMIN_PASSWORD'],
                'TZ': 'America/Vancouver',
            },
        )

        # Create the Jenkins leader service
        self.jenkins_leader_service_main = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "JenkinsleaderService",
            cpu=int(config['DEFAULT']['fargate_cpu']),
            memory_limit_mib=int(config['DEFAULT']['fargate_memory_limit_mib']),
            cluster=self.cluster.cluster,
            desired_count=1,
            enable_ecs_managed_tags=True,
            task_image_options=self.jenkins_task,
            cloud_map_options=ecs.CloudMapOptions(name="leader", dns_record_type=sd.DnsRecordType('A'))
        )

        self.jenkins_leader_service = self.jenkins_leader_service_main.service
        self.jenkins_leader_task = self.jenkins_leader_service.task_definition

        # Opening port 5000 for leader <--> worker communications
        self.jenkins_leader_service.task_definition.default_container.add_port_mappings(
            ecs.PortMapping(container_port=50000, host_port=50000)
        )

        # Enable connection between leader and Worker
        self.jenkins_leader_service.connections.allow_from(
            other=self.worker.worker_security_group,
            port_range=ec2.Port(
                protocol=ec2.Protocol.TCP,
                string_representation='leader to Worker 50000',
                from_port=50000,
                to_port=50000
            )
        )

        # Enable connection between leader and Worker on 8080
        self.jenkins_leader_service.connections.allow_from(
            other=self.worker.worker_security_group,
            port_range=ec2.Port(
                protocol=ec2.Protocol.TCP,
                string_representation='leader to Worker 8080',
                from_port=8080,
                to_port=8080
            )
        )

        # IAM Statements to allow jenkins ecs plugin to talk to ECS as well as the Jenkins cluster #
        self.jenkins_leader_task.add_to_task_role_policy(
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
                resources=[
                    "*"
                ],
            )
        )

        self.jenkins_leader_task.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ecs:ListContainerInstances"
                ],
                resources=[
                    self.cluster.cluster.cluster_arn
                ]
            )
        )

        self.jenkins_leader_task.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ecs:RunTask"
                ],
                resources=[
                    "arn:aws:ecs:{0}:{1}:task-definition/jenkins-fargate*".format(
                        self.region,
                        self.account,
            )
                ]
            )
        )

        self.jenkins_leader_task.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=[
                    "ecs:StopTask"
                ],
                resources=[
                    "arn:aws:ecs:{0}:{1}:task/*".format(
                        self.region,
                        self.account
                    )
                ],
                conditions={
                    "ForAnyValue:ArnEquals": {
                        "ecs:cluster": self.cluster.cluster.cluster_arn
                    }
                }
            )
        )

        self.jenkins_leader_task.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=[
                    "iam:PassRole"
                ],
                resources=[
                    self.worker.worker_task_role.role_arn,
                    self.worker.worker_execution_role.role_arn
                ]
            )
        )
        # END OF JENKINS ECS PLUGIN IAM POLICIES #
