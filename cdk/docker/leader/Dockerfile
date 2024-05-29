FROM --platform=linux/amd64 jenkins/jenkins:2.452.1-lts

# Install custom plugins
COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

USER root

RUN apt-get update &&\
    apt-get install -y python3-pip &&\
    pip install jinja2 dnspython --break-system-packages &&\
    rm -rf /var/lib/apt/lists/* &&\
    touch /config-as-code.yaml &&\
    chown jenkins: /config-as-code.yaml &&\
    sed -i '/\/bin\/bash*/a \\n\/modify_casc.py' /usr/local/bin/jenkins.sh

COPY modify_casc.py /modify_casc.py
COPY config-as-code.j2 /config-as-code.j2

# User back to jenkins
USER jenkins
