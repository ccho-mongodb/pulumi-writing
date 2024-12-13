import pulumi
from pulumi import automation as auto
from pulumi_aws import s3
from flask import Flask, request, make_response, jsonify
from datetime import datetime
import boto3
import botocore
import os

def ensure_plugins():
    ws = auto.LocalWorkspace()
    ws.install_plugin("aws", "v4.0.0")

# Validate server environment credentials
def ensure_aws_credentials():
    required_env_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        raise ValueError(
            f"Missing required AWS credentials: {', '.join(missing_vars)} ."
        )

    try:
        boto3.client('sts').get_caller_identity()
    except botocore.exceptions.ClientError as e:
        raise ValueError(
            f"Invalid AWS credentials. Please ensure your AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY matches a valid AWS IAM user."
            f"Error: {str(e)}"
        )
    except botocore.exceptions.NoCredentialsError:
        raise ValueError(
            "AWS credentials missing. Please set the AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables."
        )
    
ensure_plugins()
ensure_aws_credentials()

app = Flask(__name__)
PROJECT_NAME = "GeoStacks" # Fictional website builder/host

# Helper that uploads starter assets for the static website
def upload_starter_content(site_bucket: s3.BucketV2, name: str) -> s3.BucketWebsiteConfigurationV2:
    # HTML content for index.html
    content = """<!DOCTYPE html>
        <html>
        <head>
            <title>My Geostacks Website</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    text-align: center;
                    color: #0000ff;
                    background-color: #c0c0c0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Welcome to {name}'s Page</h1>
                <img src="under-construction.gif">
                <p>Under construction</p>
                <p>Created at: {timestamp}</p>
            </div>
        </body>
        </html>
        """.format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), name=name)
    
    # Configure the website settings for the bucket
    website_configuration = s3.BucketWebsiteConfigurationV2("bucketConfig",
        bucket=site_bucket.id,
        index_document=s3.BucketWebsiteConfigurationV2IndexDocumentArgs(
            suffix="index.html"
        ),
        error_document=s3.BucketWebsiteConfigurationV2ErrorDocumentArgs(
            key="error.html"
        )
    )

    # Upload index.html to the site bucket
    s3.BucketObject("index",
                    bucket=site_bucket.id,
                    content=content,
                    key="index.html",
                    content_type="text/html; charset=utf-8")

    # Upload the image to the site bucket
    s3.BucketObject("construction-img",
                    bucket=site_bucket.id,
                    source=pulumi.FileAsset('./assets/under-construction.gif'),
                    key='under-construction.gif',
    )

    return website_configuration

def set_bucket_access(site_bucket: s3.BucketV2):
    # Configure the public access block settings to allow public policies
    bucket_public_access_block = s3.BucketPublicAccessBlock(
        "exampleBucketPublicAccessBlock",
        bucket=site_bucket.id,
        block_public_acls=False,
        ignore_public_acls=False,
        block_public_policy=False,
        restrict_public_buckets=False,
        opts=pulumi.ResourceOptions(depends_on=[site_bucket])
    )

    # Set read access policy for the bucket
    s3.BucketPolicy("bucket-policy",
                    bucket=site_bucket.id,
                    policy={
                        "Version": "2012-10-17",
                        "Statement": {
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": ["s3:GetObject"],
                            "Resource": [pulumi.Output.concat("arn:aws:s3:::", site_bucket.id, "/*")]
                        },
                    },
                    opts=pulumi.ResourceOptions(depends_on=[bucket_public_access_block])
    )
    # Note: intentionally omitted versioning to keep the code concise

# Create a static website on S3, customized by the passed parameter.
def create_pulumi_program(name: str):
    site_bucket = s3.BucketV2("s3-website-bucket")

    website_config = upload_starter_content(site_bucket, name)

    set_bucket_access(site_bucket)

    pulumi.export("website_url", website_config.website_endpoint)

@app.route("/sites", methods=["GET"])
def list_handler():
    """lists all sites"""
    try:
        ws = auto.LocalWorkspace(project_settings=auto.ProjectSettings(name=PROJECT_NAME, runtime="python"))
        stacks = ws.list_stacks()
        return jsonify(ids=[stack.name for stack in stacks])
    except Exception as exn:
        return make_response(str(exn), 500)

@app.route("/site", methods=["POST"])
def create_handler():
    name = request.json.get('username')

    try:
        def pulumi_program():
            return create_pulumi_program(name)
        # create a new stack, generating our pulumi program on the fly from the POST body
        stack = auto.create_stack(stack_name=name,
                                  project_name=PROJECT_NAME,
                                  program=pulumi_program)
        stack.set_config("aws:region", auto.ConfigValue("us-west-2"))
        # deploy the stack, tailing the logs to stdout
        up_res = stack.up(on_output=print)
        return jsonify(id=name, url=up_res.outputs['website_url'].value)
    except auto.StackAlreadyExistsError:
        return make_response(f"Stack '{name}' already exists", 409)
    except Exception as exn:
        return make_response(str(exn), 500)

@app.route("/site/<string:id>", methods=["GET"])
def get_handler(id: str):
    stack_name = id

    try:
        stack = auto.select_stack(stack_name=stack_name,
                                  project_name=PROJECT_NAME,
                                  # no-op program, just to get outputs
                                  program=lambda *args: None)
        outs = stack.outputs()
        return jsonify(id=stack_name, url=outs["website_url"].value)
    except auto.StackNotFoundError:
        return make_response(f"stack '{stack_name}' does not exist", 404)
    except Exception as exn:
        print(exn)
        return make_response(str(exn), 500)

# Omitted the update endpoint since updating S3 assets with the AWS S3 SDK makes more sense

@app.route("/site/<string:id>", methods=["DELETE"])
def delete_handler(id: str):
    stack_name = id
    try:
        stack = auto.select_stack(stack_name=stack_name,
                                  project_name=PROJECT_NAME,
                                  # noop program for destroy
                                  program=lambda *args: None)
        stack.destroy(on_output=print)
        stack.workspace.remove_stack(stack_name)
        return jsonify(message=f"Stack '{stack_name}' resources successfully removed!")
    except auto.StackNotFoundError:
        return make_response(f"Stack '{stack_name}' does not exist", 404)
    except auto.ConcurrentUpdateError:
        return make_response(f"Stack '{stack_name}' already has update in progress", 409)
    except Exception as exn:
        return make_response(str(exn), 500)