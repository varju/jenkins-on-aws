from configparser import ConfigParser

from aws_cdk import (
    aws_ecs,
    Stack,
)
from constructs import Construct

from .network import Network

config = ConfigParser()
config.read("config.ini")


class ECSCluster(Construct):

    def __init__(self, scope: Stack, network: Network, service_discovery_namespace):
        super().__init__(scope, "ECSCluster")

        self.cluster = aws_ecs.Cluster(
            self,
            "Cluster",
            vpc=network.vpc,
            default_cloud_map_namespace=aws_ecs.CloudMapNamespaceOptions(
                name=service_discovery_namespace
            ),
        )
