FROM --platform=linux/amd64 jenkins/inbound-agent as inbound-agent

FROM 392477962641.dkr.ecr.us-east-1.amazonaws.com/saas/corretto-java11-build:3194

COPY --from=inbound-agent /usr/share/jenkins/agent.jar /usr/share/jenkins/agent.jar
COPY --from=inbound-agent /usr/local/bin/jenkins-agent /usr/local/bin/jenkins-agent
RUN rm -f /home/jenkins/workspace

ENTRYPOINT ["/usr/local/bin/jenkins-agent"]
