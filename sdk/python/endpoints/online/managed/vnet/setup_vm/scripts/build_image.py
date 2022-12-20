#!/opt/anaconda/envs/vnet/bin/python

import argparse
from azure.mgmt.containerregistry import ContainerRegistryManagementClient
from azure.identity import ManagedIdentityCredential
from azure.mgmt.containerregistry.models import DockerBuildRequest, Credentials, SourceRegistryCredentials, PlatformProperties
from azure.storage.blob import upload_blob_to_url
import uuid, time, os, tarfile

parser = argparse.ArgumentParser()
parser.add_argument('--subscription_id', type=str, default=os.getenv("SUBSCRIPTION_ID"))
parser.add_argument('--resource_group', type=str, default=os.getenv("RESOURCE_GROUP"))
parser.add_argument('--container_registry', type=str, default=os.getenv("CONTAINER_REGISTRY") )
parser.add_argument('--image_name', type=str, default=os.getenv("IMAGE_NAME"))
parser.add_argument('--env_dir_path', type=str, default=os.getenv("ENV_DIR_PATH"))
args = parser.parse_args()

credential = ManagedIdentityCredential()
cr_client = ContainerRegistryManagementClient(credential, args.subscription_id)

# <upload_source>
tar_path = f"/tmp/{uuid.uuid4()}.tar.gz"
source_url = cr_client.registries.get_build_source_upload_url(registry_name=args.container_registry,resource_group_name=args.resource_group)

with tarfile.open(tar_path, "w:gz") as f:
    f.add(args.env_dir_path,arcname="")

with open(tar_path, "rb") as f: 
    upload_blob_to_url(source_url.upload_url, f)

image_tag = f"{args.container_registry}.azurecr.io/{args.image_name}:latest"
# </upload_source>

# <build_image>
build_request = DockerBuildRequest(
    docker_file_path="Dockerfile",
    platform=PlatformProperties(
        os="Linux",
        architecture="amd64"
    ),
    is_push_enabled=True,
    image_names=[image_tag],
    source_location=source_url.relative_path,
    credentials = Credentials(source_registry=SourceRegistryCredentials(login_mode="Default")),
    timeout=300,
)
run = cr_client.registries.begin_schedule_run(registry_name=args.container_registry,resource_group_name=args.resource_group,run_request=build_request).result()
# </build_image> 

run_status = ""
elapsed = 0
while cr_client.runs.get(run_id=run.name,registry_name=args.container_registry,resource_group_name=args.resource_group).status != "Succeeded":
    time.sleep(5)
    elapsed += 5
    if elapsed > 300:
        raise RuntimeError("Build timed out")