FROM --platform=linux/amd64 jenkins/inbound-agent

USER root

RUN apt-get update && \
    apt-get install -y postgresql-client-15 && \
    rm -rf /var/lib/apt/lists/*

USER jenkins
