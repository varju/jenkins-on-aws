#!/usr/bin/env python3

from os import getenv
from configparser import ConfigParser

from aws_cdk import (
    App,
    Tags,
)

from jenkins.network import Network
from jenkins.ecs import ECSCluster
from jenkins.jenkins_leader import JenkinsLeader
from jenkins.jenkins_worker import JenkinsWorker

config = ConfigParser()
config.read('config.ini')

stack_name = config['DEFAULT']['stack_name']
account = getenv('CDK_DEFAULT_ACCOUNT')
region = getenv('CDK_DEFAULT_REGION')

service_discovery_namespace = 'jenkins'

app = App()
network = Network(app, stack_name + 'Network')
ecs_cluster = ECSCluster(app, stack_name + 'ECS', vpc=network.vpc, service_discovery_namespace=service_discovery_namespace)
jenkins_workers = JenkinsWorker(app, stack_name + "Worker", vpc=network.vpc, cluster=ecs_cluster)
jenkins_leader_service = JenkinsLeader(app, stack_name + 'JenkinsLeader', cluster=ecs_cluster, vpc=network, worker=jenkins_workers)

Tags.of(app).add(key='Name', value=stack_name)
Tags.of(app).add(key='Department', value='501')
Tags.of(app).add(key='DevTeam', value='Voyager')
Tags.of(app).add(key='Environment', value='Development')

app.synth()
