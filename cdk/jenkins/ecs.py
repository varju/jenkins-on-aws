from configparser import ConfigParser

from aws_cdk import (
    aws_ecs,
    Stack,
)
from constructs import Construct

config = ConfigParser()
config.read('config.ini')


class ECSCluster(Stack):

    def __init__(self, scope: Construct, id: str, vpc, service_discovery_namespace, **kwargs):
        super().__init__(scope, id, **kwargs)
        self.vpc = vpc
        self.service_discovery_namespace = service_discovery_namespace

        # Create VPC for cluster - best practice is to isolate jenkins to its own vpc
        self.cluster = aws_ecs.Cluster(
            self, "ECSCluster",
            vpc=self.vpc,
            default_cloud_map_namespace=aws_ecs.CloudMapNamespaceOptions(name=service_discovery_namespace)
        )
