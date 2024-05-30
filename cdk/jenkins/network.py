from configparser import ConfigParser

from aws_cdk import (
    aws_ec2,
    Stack,
)
from constructs import Construct

config = ConfigParser()
config.read('config.ini')


class Network(Stack):

    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        self.vpc = aws_ec2.Vpc(
            self, "Vpc",
            ip_addresses=aws_ec2.IpAddresses.cidr(config['DEFAULT']['cidr']),
        )

