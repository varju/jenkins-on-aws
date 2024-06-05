from aws_cdk import (
    aws_autoscaling as autoscaling,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_efs as efs,
    aws_logs as logs,
    RemovalPolicy,
    Stack,
)
from constructs import Construct

from .network import Network


class ECSCluster(Construct):

    def __init__(self, scope: Stack, network: Network, service_discovery_namespace):
        super().__init__(scope, "ECSCluster")

        self.exec_log_group = logs.LogGroup(
            self,
            "ExecLogGroup",
            retention=logs.RetentionDays.ONE_MONTH,
        )

        self.cluster = ecs.Cluster(
            self,
            "Cluster",
            vpc=network.vpc,
            default_cloud_map_namespace=ecs.CloudMapNamespaceOptions(
                name=service_discovery_namespace
            ),
            container_insights=True,
            execute_command_configuration=ecs.ExecuteCommandConfiguration(
                logging=ecs.ExecuteCommandLogging.OVERRIDE,
                log_configuration=ecs.ExecuteCommandLogConfiguration(
                    cloud_watch_log_group=self.exec_log_group
                ),
            ),
        )

        self.filesystem = efs.FileSystem(
            self,
            "FileSystem",
            vpc=network.vpc,
            encrypted=True,
            lifecycle_policy=efs.LifecyclePolicy.AFTER_7_DAYS,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # EC2 backend for agents
        self.asg = autoscaling.AutoScalingGroup(
            self,
            "ASG",
            instance_type=ec2.InstanceType("t3.xlarge"),
            machine_image=ecs.EcsOptimizedImage.amazon_linux2023(),
            min_capacity=1,
            max_capacity=4,
            vpc=network.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            ssm_session_permissions=True,
        )

        self.capacity_provider = ecs.AsgCapacityProvider(
            self,
            "AsgCapacityProvider",
            auto_scaling_group=self.asg,
            enable_managed_draining=False,
            instance_warmup_period=60,
        )
        self.cluster.add_asg_capacity_provider(self.capacity_provider)
        self.cluster.add_default_capacity_provider_strategy(
            [
                ecs.CapacityProviderStrategy(
                    capacity_provider=self.capacity_provider.capacity_provider_name
                )
            ]
        )
