from configparser import ConfigParser

from aws_cdk import (
    aws_ecr_assets as ecr,
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_logs as logs,
    Stack,
)
from constructs import Construct

from .network import Network

config = ConfigParser()
config.read("config.ini")


class JenkinsAgent(Construct):

    def __init__(self, scope: Stack, network: Network) -> None:
        super().__init__(scope, "Agent")

        # Security group to connect agents to controller
        self.security_group = ec2.SecurityGroup(
            self,
            "SecurityGroup",
            vpc=network.vpc,
            description="Jenkins Agent access to Jenkins Controller",
        )

        # IAM execution role for the agents to pull from ECR and push to CloudWatch logs
        self.execution_role = iam.Role(
            self,
            "ExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        self.execution_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name(
                "service-role/AmazonECSTaskExecutionRolePolicy"
            )
        )

        # Task role for agent containers - add to this role for any aws resources that jenkins requires access to
        self.task_role = iam.Role(
            self,
            "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # Create log group for agents to log
        self.log_group = logs.LogGroup(
            self,
            "LogGroup",
            retention=logs.RetentionDays.ONE_DAY,
        )

        # Create log stream for agent log group
        self.log_stream = logs.LogStream(
            self,
            "LogStream",
            log_group=self.log_group,
        )

        self.simple_agent = DockerAgent(self, "Simple", "docker/agents/simple")


class DockerAgent(Construct):
    def __init__(self, scope: Construct, id: str, directory: str) -> None:
        super().__init__(scope, id)

        self.container_image = ecr.DockerImageAsset(
            self, "DockerImage", directory=directory
        )
