from configparser import ConfigParser

from aws_cdk import (
    aws_ec2,
    Stack,
)
from constructs import Construct

config = ConfigParser()
config.read("config.ini")


class Network(Construct):

    def __init__(self, scope: Stack):
        super().__init__(scope, "Network")

        self.vpc = aws_ec2.Vpc(
            self,
            "Vpc",
            ip_addresses=aws_ec2.IpAddresses.cidr(config["DEFAULT"]["cidr"]),
        )
