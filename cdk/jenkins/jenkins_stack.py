from aws_cdk import Stack
from constructs import Construct

from .codebuild import CodeBuild
from .ecs import ECSCluster
from .jenkins_agent import JenkinsAgent
from .jenkins_controller import JenkinsController
from .network import Network

service_discovery_namespace = "jenkins"


class JenkinsStack(Stack):

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        network = Network(self)
        ecs_cluster = ECSCluster(
            self,
            network=network,
            service_discovery_namespace=service_discovery_namespace,
        )
        agent = JenkinsAgent(
            self,
            network=network,
        )
        codebuild = CodeBuild(self, agent)
        JenkinsController(
            self,
            ecs_cluster=ecs_cluster,
            network=network,
            agent=agent,
            codebuild=codebuild,
        )
