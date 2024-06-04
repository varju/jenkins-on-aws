from configparser import ConfigParser

from aws_cdk import (
    aws_ecr_assets as ecr,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_iam as iam,
    aws_logs as logs,
    Stack,
)
from constructs import Construct

from .network import Network

config = ConfigParser()
config.read("config.ini")


class JenkinsAgent(Construct):
    def __init__(self, stack: Stack, network: Network) -> None:
        super().__init__(stack, "Agent")

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

        self.simple_agent = SimpleAgent(self)
        self.java11_agent = Java11Agent(self)
        self.postgres12_task_def = Postgres12TaskDefinition(self, stack)


class SimpleAgent(Construct):
    def __init__(self, scope: JenkinsAgent) -> None:
        super().__init__(scope, "Simple")

        self.container_image = ecr.DockerImageAsset(
            self, "DockerImage", directory="docker/agents/simple"
        )


class Java11Agent(Construct):
    def __init__(self, scope: JenkinsAgent) -> None:
        super().__init__(scope, "Java11")

        self.container_image = ecr.DockerImageAsset(
            self, "DockerImage", directory="docker/agents/java11"
        )


class Postgres12TaskDefinition(Construct):
    """
    This example weaves together sidecar containers that can be used from Jenkins.
    """

    def __init__(self, scope: JenkinsAgent, stack: Stack) -> None:
        super().__init__(scope, "Complex")

        self.task_def = ecs.FargateTaskDefinition(
            self,
            "TaskDef",
            family=f"{stack.stack_name}-complex-agent",
            cpu=2048,
            memory_limit_mib=4096,
            task_role=scope.task_role,
            execution_role=scope.execution_role,
        )

        logging = ecs.LogDrivers.aws_logs(
            stream_prefix="complex",
            log_group=scope.log_group,
        )
        self.task_def.add_container(
            "jnlp",
            image=ecs.ContainerImage.from_docker_image_asset(
                ecr.DockerImageAsset(
                    self, "JnlpImage", directory="docker/agents/postgres12/jnlp"
                )
            ),
            logging=logging,
        )
        self.task_def.add_container(
            "postgres",
            image=ecs.ContainerImage.from_docker_image_asset(
                ecr.DockerImageAsset(
                    self, "PostgresImage", directory="docker/agents/postgres12/postgres"
                )
            ),
            environment={
                "POSTGRES_PASSWORD": "password",
            },
            logging=logging,
        )
