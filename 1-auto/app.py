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
PROJECT_NAME = "Geostacks" # Fictional website builder/host

def upload_starter_content(site_bucket, name):
    content = """<!DOCTYPE html>
        <html>
        <head>
            <title>My Geostacks Website</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 2rem;
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
    
    bucket_versioning = s3.BucketVersioningV2(
        "exampleBucketVersioning",
        bucket=site_bucket.id,
        versioning_configuration={
            "status": "Enabled",
        }
    )

    # Configure the website settings for the bucket
    website_configuration = s3.BucketWebsiteConfigurationV2("bucketConfig",
        bucket=site_bucket.id,
        opts=pulumi.ResourceOptions(depends_on=[bucket_versioning]),
        index_document=s3.BucketWebsiteConfigurationV2IndexDocumentArgs(
            suffix="index.html"
        ),
        error_document=s3.BucketWebsiteConfigurationV2ErrorDocumentArgs(
            key="error.html"
        )
    )

    # Define the bucket policy to make the objects publicly accessible
    bucket_policy = s3.BucketPolicy("bucketPolicy",
        bucket=website_configuration.id,
        policy=website_configuration.id.apply(lambda id: f"""
            {{
                "Version": "2012-10-17",
                "Statement": [
                    {{
                        "Effect": "Allow",
                        "Principal": "*",
                        "Action": "s3:GetObject",
                        "Resource": "arn:aws:s3:::{id}/*"
                    }}
                ]
            }}
            """)
    )

    # Write our index.html into the site bucket
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


# This function defines our pulumi s3 static website in terms of the content that the caller passes in.
# This allows us to dynamically deploy websites based on user defined values from the POST body.
def create_pulumi_program(name: str):
    # Create a bucket and expose a website index document
    site_bucket = s3.Bucket("s3-website-bucket", website=s3.BucketWebsiteArgs(index_document="index.html"))

    upload_starter_content(site_bucket, name)

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
    
    # Set the access policy for the bucket so all objects are readable
    s3.BucketPolicy("bucket-policy",
                    bucket=site_bucket.id,
                    policy={
                        "Version": "2012-10-17",
                        "Statement": {
                            "Effect": "Allow",
                            "Principal": "*",
                            "Action": ["s3:GetObject"],
                            # Policy refers to bucket explicitly
                            "Resource": [pulumi.Output.concat("arn:aws:s3:::", site_bucket.id, "/*")]
                        },
                    },
                    opts=pulumi.ResourceOptions(depends_on=[bucket_public_access_block])
        )

    # Export the website URL
    pulumi.export("website_url", site_bucket.website_endpoint)

@app.route("/sites", methods=["GET"])
def list_handler():
    """lists all sites"""
    try:
        ws = auto.LocalWorkspace(project_settings=auto.ProjectSettings(name=PROJECT_NAME, runtime="python"))
        stacks = ws.list_stacks()
        return jsonify(ids=[stack.name for stack in stacks])
    except Exception as exn:
        return make_response(str(exn), 500)
    
@app.route("/sites", methods=["POST"])
def create_handler():
    """creates new sites"""
    stack_name = request.json.get('id')
    username = request.json.get('username')
    try:
        def pulumi_program():
            return create_pulumi_program(username)
        # create a new stack, generating our pulumi program on the fly from the POST body
        stack = auto.create_stack(stack_name=stack_name,
                                  project_name=PROJECT_NAME,
                                  program=pulumi_program)
        stack.set_config("aws:region", auto.ConfigValue("us-west-2"))
        # deploy the stack, tailing the logs to stdout
        up_res = stack.up(on_output=print)
        return jsonify(id=stack_name, url=up_res.outputs['website_url'].value)
    except auto.StackAlreadyExistsError:
        return make_response(f"Stack '{stack_name}' already exists", 409)
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
        print("outs: ", outs)
        return jsonify(id=stack_name, url=outs["website_url"].value)
    except auto.StackNotFoundError:
        return make_response(f"stack '{stack_name}' does not exist", 404)
    except Exception as exn:
        print(exn)
        return make_response(str(exn), 500)

# Intentionally disabled since updating S3 assets with the AWS S3 SDK makes more sense
# @app.route("/site/<string:id>", methods=["UPDATE"])

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