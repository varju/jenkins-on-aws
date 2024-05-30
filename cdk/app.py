#!/usr/bin/env python3

from configparser import ConfigParser

from aws_cdk import (
    App,
    Tags,
)

from jenkins.jenkins_stack import JenkinsStack

config = ConfigParser()
config.read("config.ini")


app = App()
JenkinsStack(app, config["DEFAULT"]["stack_name"])

Tags.of(app).add(key="Department", value="501")
Tags.of(app).add(key="DevTeam", value="Voyager")
Tags.of(app).add(key="Environment", value="Development")

app.synth()
