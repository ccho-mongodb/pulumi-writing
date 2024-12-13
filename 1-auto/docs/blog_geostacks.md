Building a Web Hosting Service Using the Automation API
=======================================================

> **Note**
> The **GeoStacks** company and all individuals mentioned in this blog post are fictional.

After immense growth in popularity, the free web hosting service startup **GeoStacks**
was ready for its next evolution, which was to keep up with 100,000 new user registrations
daily. Every user registration or account deletion triggered a text message that informed
the engineering team that they needed to provision or destroy the website resources 
manually on Amazon S3.

"Our DevOps team developed a fear of text message notifications and couldn't stand 
another hour on the Amazon AWS console. And our users couldn't wait another moment to
establish their online presence. We needed to application-level automation right away," 
Eureka Petsburgh, Geostacks' CTO remarked. While exploring solutions, Eureka discovered
that the Pulumi Automation API enabled engineers to automate infrastructure management
in code.

The GeoStacks engineers replaced the text message flow with a RESTful web service that
provisioned and deleted websites using the Pulumi Automation API. Eureka estimates this
solution saves them 100 work hours per day and reduces the turnaround from an hour to
less than one minute. The GeoStacks engineering team recently shared their journey to 
implementing it with us.

# Introduction to the Pulumi Automation API

The **Pulumi Automation API** lets you call Pulumi lifecycle commands and **Pulumi programs** 
from an application using SDKs written for various languages. A Pulumi program is a
collection of code that defines the cloud resources, configurations, and relationships to 
deploy. It runs in a **Pulumi stack**, a configurable instance of a Pulumi program.

One of the various ways you can use the Automation API is by inlining a Pulumi program in 
your application code. The program runs in a **Workspace**, the execution context that
includes project settings and configuration data.

# GeoStacks Infrastructure as Code Web Service

The GeoStacks RESTful web service accepts calls from the GeoStacks User Service to
create, retrieve, and delete infrastructure associated with a user. The following
sections explain the implementation of each action.

## Create: S3 Website Provisioning

When creating a new user website in the GeoStacks web service, the endpoint instantiates
an inline Pulumi program, customized by the new username. Then, it associates the program,
a callback to run once the operation succeeds, to the stack as shown in the following
Python code:
\
```python
    from pulumi import automation as auto

    def pulumi_program():
        return create_pulumi_program(username)
    stack = auto.create_stack(stack_name=stack_name,
                                  project_name="GeoStacks",
                                  program=pulumi_program)
```

The ``create_pulumi_program()`` method referenced by the prior code sample performs the
following actions:

- Create an Amazon S3 bucket
- Upload the website assets
- Create a bucket policy to make the site publicly viewable

```python
    from pulumi_aws import s3

    site_bucket = s3.BucketV2("my-s3-website-bucket")
    website_config = upload_starter_content(site_bucket, name)
    set_bucket_access(site_bucket)
```


## Retrieve: S3 Website Listing

The RESTful web service features an endpoint that retrieves the S3 bucket information for 
all current sites on the Pulumi ``LocalWorkspace``. It retrieves all the stacks in the
specified project from the Automation API and resembles the following code:

```python
    from pulumi import automation as auto

    ws = auto.LocalWorkspace(project_settings=auto.ProjectSettings(name="GeoStacks"", runtime="python"))
    stacks = ws.list_stacks()
```

The web service offers an endpoint to retrieve the public URL by the stack name as shown
in the following code:

```python
        stack = auto.select_stack(stack_name=stack_name,
                                  project_name="GeoStacks"",
                                  program=lambda *args: None)
        outs = stack.outputs()
        return jsonify(id=stack_name, url=outs["website_url"].value)
```

## Delete: S3 Website Removal

*TODO: describe the destroy() method using a similar format to the prior sections*


## GeoStacks Web Service in Action

<!-- 
TODO: Explain setup steps such as dependency installation, AWS IAM user credential setup 
for the app, and Pulumi login

Clone the [GeoStacks web service source code](https://github.com/ccho-mongodb/pulumi-writing/tree/main/1-auto) from GitHub.

TODO: List the curl commands to perform actions 

-->

Open the URL returned by the response to your successful ``POST`` request to ``site/`` in your browser.
You should see a web page that resembles the following:

![Screenshot of a GeoStacks sample website](https://github.com/ccho-mongodb/pulumi-writing/blob/main/docs/geostacks_site.png?raw=true)


<!--

curl --header "Content-Type: application/json" \
  --request POST \
  --data '{"username": "chris"}' \
  http://127.0.0.1:5000/site


Sample response:
```
{"id":"chris","url":"s3-website-bucket-abc.s3-website-us-west-2.amazonaws.com"}
```

Sample output:
```
 +  pulumi:pulumi:Stack GeoStacks-chris creating (0s)
@ Updating.....
 +  aws:s3:BucketV2 s3-website-bucket creating (0s)
@ Updating......
 +  aws:s3:BucketV2 s3-website-bucket created (2s)
 +  aws:s3:BucketPublicAccessBlock exampleBucketPublicAccessBlock creating (0s)
 +  aws:s3:BucketObject index creating (0s)
 +  aws:s3:BucketWebsiteConfigurationV2 bucketConfig creating (0s)
 +  aws:s3:BucketObject construction-img creating (0s)
@ Updating....
 +  aws:s3:BucketPublicAccessBlock exampleBucketPublicAccessBlock created (0.78s)
 +  aws:s3:BucketObject index created (0.94s)
 +  aws:s3:BucketWebsiteConfigurationV2 bucketConfig created (1s)
 +  aws:s3:BucketPolicy bucket-policy creating (0s)
 +  aws:s3:BucketObject construction-img created (1s)
@ Updating....
 +  aws:s3:BucketPolicy bucket-policy created (1s)
@ Updating......
 +  pulumi:pulumi:Stack GeoStacks-chris created (8s)
Outputs:
    website_url: "s3-website-bucket-abc.s3-website-us-west-2.amazonaws.com"

Resources:
    + 7 created

Duration: 9s
```

curl -X DELETE http://127.0.0.1:5000/site/chris

Sample response:
```
{"message":"Stack 'chris' resources successfully removed!"}
```

Sample output:

```
@ Destroying....
 -  aws:s3:BucketPolicy bucket-policy deleting (0s)
 -  aws:s3:BucketPolicy bucket-policy deleted (0.84s)
@ Destroying....
 -  aws:s3:BucketPublicAccessBlock exampleBucketPublicAccessBlock deleting (0s)
 -  aws:s3:BucketWebsiteConfigurationV2 bucketConfig deleting (0s)
 -  aws:s3:BucketObject construction-img deleting (0s)
 -  aws:s3:BucketObject index deleting (0s)
 -  aws:s3:BucketPublicAccessBlock exampleBucketPublicAccessBlock deleted (0.58s)
 -  aws:s3:BucketWebsiteConfigurationV2 bucketConfig deleted (0.61s)
@ Destroying....
 -  aws:s3:BucketObject construction-img deleted (0.83s)
 -  aws:s3:BucketObject index deleted (1s)
@ Destroying....
 -  aws:s3:BucketV2 s3-website-bucket deleting (0s)
 -  aws:s3:BucketV2 s3-website-bucket deleted (0.52s)
 -  pulumi:pulumi:Stack GeoStacks-chris deleting (0s)
@ Destroying....
 -  pulumi:pulumi:Stack GeoStacks-chris deleted (0.16s)
Outputs:
  - website_url: "s3-website-bucket-abc.s3-website-us-west-2.amazonaws.com"

Resources:
    - 7 deleted

Duration: 6s
```

--> 
# Additional Resources

- To learn more about the Pulumi Automation API terminology, see [Automation API concepts & terminology](https://www.pulumi.com/docs/iac/packages-and-automation/automation-api/concepts-terminology/).

- *TODO: Add additional links with descriptions for concepts mentioned in this blog post*