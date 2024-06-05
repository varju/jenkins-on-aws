#!/usr/bin/env python3

from jinja2 import Environment, FileSystemLoader
from os import getenv


def main():
    # This value comes as a build env var: `SSM_CONFIG_PARAM_NAME`
    _env = Environment(loader=FileSystemLoader("/"), autoescape=True)
    _template = _env.get_template("/config-as-code.j2")
    _config_file = open("/config-as-code.yaml", "w")

    _config_file.write(
        (
            _template.render(
                STACK_NAME=getenv("stack_name"),
                ECS_CLUSTER_ARN=getenv("cluster_arn"),
                AWS_REGION=getenv("aws_region"),
                JENKINS_URL=getenv("jenkins_url"),
                JENKINS_PUBLIC_URL=getenv("jenkins_public_url"),
                SUBNET_IDS=getenv("subnet_ids"),
                SECURITY_GROUP_IDS=getenv("security_group_ids"),
                EXECUTION_ROLE_ARN=getenv("execution_role_arn"),
                TASK_ROLE_ARN=getenv("task_role_arn"),
                LOG_GROUP=getenv("agent_log_group"),
                LOG_STREAM_PREFIX=getenv("agent_log_stream_prefix"),
                ADMIN_USERNAME=getenv("admin_username"),
                ADMIN_PASSWORD=getenv("admin_password"),
                SIMPLE_AGENT_IMAGE=getenv("simple_agent_image"),
                POSTGRES12_TASK_DEF=getenv("postgres12_task_def"),
                AGENT_IMAGE_JAVA_11=getenv("agent_image_java_11"),
                GH_CREDENTIAL_ID=getenv("gh_credential_id"),
                GH_CREDENTIAL_APP_ID=getenv("gh_credential_app_id"),
                GH_CREDENTIAL_PRIVATE_KEY=getenv("gh_credential_private_key"),
                GH_CREDENTIAL_OWNER=getenv("gh_credential_owner"),
                CODEBUILD_PROJECT_NAME=getenv("codebuild_project_name"),
            )
        )
    )

    _config_file.close()


if __name__ == "__main__":
    main()
