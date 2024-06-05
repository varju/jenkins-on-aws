from aws_cdk import (
    aws_codebuild as codebuild,
    aws_iam as iam,
    Stack,
)
from constructs import Construct


class CodeBuild(Construct):
    def __init__(self, stack: Stack) -> None:
        super().__init__(stack, "CodeBuild")

        self.project = codebuild.Project(
            self,
            "Project",
            project_name=f"{stack.stack_name}-build",
            build_spec=codebuild.BuildSpec.from_object(
                {
                    "version": "0.2",
                    "phases": {
                        "build": {
                            "commands": ["exit 1"],
                        },
                    },
                }
            ),
        )

        # Allow pushes
        self.project.role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=[
                    "ecr:BatchCheckLayerAvailability",
                    "ecr:CompleteLayerUpload",
                    "ecr:InitiateLayerUpload",
                    "ecr:PutImage",
                    "ecr:UploadLayerPart",
                ],
                resources=[
                    f"arn:aws:ecr:{stack.region}:{stack.account}:repository/{stack.stack_name}*",
                ],
            )
        )
        self.project.role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"],
            ),
        )
