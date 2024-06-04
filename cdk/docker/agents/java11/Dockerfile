FROM 392477962641.dkr.ecr.us-east-1.amazonaws.com/saas/corretto-java11-build:3194

RUN \
  curl --location --show-error --silent \
    --output /usr/share/jenkins/upstream-jnlp-start \
    https://raw.githubusercontent.com/jenkinsci/docker-agent/5c3469aa6b314fa2686b0565f41d9f3bd10a1a86/jenkins-agent \
  && chmod +x /usr/share/jenkins/upstream-jnlp-start

COPY jnlp-start /usr/share/jenkins/jnlp-start

ENTRYPOINT ["/usr/share/jenkins/jnlp-start"]
