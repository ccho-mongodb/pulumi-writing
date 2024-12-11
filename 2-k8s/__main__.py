import pulumi
import pulumi_aws as aws
import pulumi_awsx as awsx
import pulumi_eks as eks
import pulumi_kubernetes as k8s
import pulumi_docker as docker


# Pre-requisite: upload the flask_app Docker image to ECR and replace the repo_name and image_name values

repo_name = "ccho-aws/my-images"
image_name = "682033509293.dkr.ecr.us-east-1.amazonaws.com/ccho-aws/my-images:latest"

# Get ECR image
repo = awsx.ecr.Repository("ccho-aws/my-images")
my_image = docker.RemoteImage("my-image", name=image_name) 

# Set up VPC
my_vpc = awsx.ec2.Vpc("my_vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_hostnames=True,
    number_of_availability_zones=2,
    nat_gateways=1,
    tags={
        "name": "my-k8s-vpc",
})

# Create an EKS cluster.
cluster = eks.Cluster('my-cluster',
    vpc_id=my_vpc.vpc_id,
    public_subnet_ids=my_vpc.public_subnet_ids,
    private_subnet_ids=my_vpc.private_subnet_ids,
    instance_type="t3.small",
    desired_capacity=1,
    min_size=1,
    max_size=2,
)

# Deploy app to Kubernetes
app_labels = {"app": "pulumi-assignment-app"}
deployment = k8s.apps.v1.Deployment("app-deployment",
    spec=k8s.apps.v1.DeploymentSpecArgs(
        selector=k8s.meta.v1.LabelSelectorArgs(
            match_labels=app_labels
        ),
        replicas=1,
        template=k8s.core.v1.PodTemplateSpecArgs(
            metadata=k8s.meta.v1.ObjectMetaArgs(
                labels=app_labels
            ),
            spec=k8s.core.v1.PodSpecArgs(
                containers=[k8s.core.v1.ContainerArgs(
                    name="flask-app",
                    image=my_image,
                    ports=[k8s.core.v1.ContainerPortArgs(
                        container_port=8080
                    )]
                )]
            )
        )
    )
)

pulumi.export('kubeconfig', cluster.kubeconfig)  # kubeconfig
