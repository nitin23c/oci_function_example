import io
import json
import logging
import oci
import paramiko
import os
import base64
import time

import oci.object_storage
from fdk import response

def download_objects(signer, namespace, src_bucket):
    try:
        object_storage = oci.object_storage.ObjectStorageClient(config={}, signer=signer)
        objects = object_storage.list_objects(namespace_name=namespace, bucket_name=src_bucket)
        for obj in objects.data.objects:
            object_name = obj.name
            local_path = os.environ.get("LOCAL_PATH")
            object_path = os.path.join(local_path, object_name)
            object_size = obj.size
            logging.info(f"Downloading {object_name}")
            response = object_storage.get_object(namespace_name=namespace, bucket_name=src_bucket, object_name=object_name)
            with open(object_path, 'wb') as f:
                f.write(response.data.content)
            logging.info(f"Downloaded {object_name}")
            yield object_name

    except (Exception, ValueError) as ex:
        logging.error(str(ex))
        return {"response": str(ex)}

    return {"response": str(response)}

def delete_objects(signer, namespace, src_bucket, object_names):
    object_storage = oci.object_storage.ObjectStorageClient(config={}, signer=signer)
    for object_name in object_names:
        object_storage.delete_object(namespace, src_bucket, object_name)
        logging.info(f"Deleted {object_name} in bucket {src_bucket}")

def delete_local_files(local_path, object_name):
    for file_name in object_name:
        file_name = os.path.join(local_path, file_name)
        os.remove(file_name)
        logging.info(f"Deleted {file_name} in container")

def upload_objects(signer, namespace, remote_host, remote_path, object_names, remote_user, local_path):
    secret_ocid = os.environ.get("SECRET_OCID")
    try:
        get_secret = oci.secrets.SecretsClient({}, signer=signer)
        secret_content = get_secret.get_secret_bundle(secret_ocid).data.secret_bundle_content.content.encode('ascii')
        decrypted_secret_content = base64.b64decode(secret_content).decode("ascii")
        print("decrypted secret content is:", decrypted_secret_content)
        with open('/tmp/remote_server.key', 'w') as file:
            file.write(decrypted_secret_content)
    except Exception as ex:
        print("ERROR: failed to retrieve the secret content", ex, flush=True)
        raise
    # Set the permissions of the temporary file to 0600
    os.chmod('/tmp/remote_server.key', 0o600)
    ssh_key_path = os.path.join(local_path, 'remote_server.key')
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_key = paramiko.RSAKey.from_private_key_file(ssh_key_path)
    ssh_client.connect(remote_host, username=remote_user, pkey=ssh_key)

    try:
        sftp_client = ssh_client.open_sftp()
        for file_name in object_names:
            file_name = os.path.join(local_path, file_name)
            remote_file_path = os.path.join(remote_path, file_name)
            logging.info(f"Uploading {file_name} to {remote_user}@{remote_host}:{remote_file_path}")
            sftp_client.put(file_name, remote_file_path)
            logging.info(f"Uploaded {file_name} to {remote_user}@{remote_host}:{remote_file_path}")
        sftp_client.close()

    except Exception as e:
        logging.error(f"Error while uploading objects: {e}")

    finally:
        ssh_client.close()

def handler(ctx, data: io.BytesIO=None):
    signer = oci.auth.signers.get_resource_principals_signer()
    resp   = ""
    try:
        # Fetch and set all the required variables
        body        = json.loads(data.getvalue())
        
        # Fetches config from event attributes
        namespace   = body["data"]["additionalDetails"]["namespace"]
        src_bucket  = body["data"]["additionalDetails"]["bucketName"]

        #Fetches config from func.yaml config section
        local_path = os.environ.get("LOCAL_PATH")
        remote_host = os.environ.get("REMOTE_HOST")
        remote_path = os.environ.get("REMOTE_PATH")
        remote_user = os.environ.get("REMOTE_USER")
    
        logging.getLogger('oci').setLevel(logging.INFO)
        logging.getLogger('paramiko').setLevel(logging.INFO)

        # define an array to store all object names from bucket
        object_names = []

        # store all object name in array
        for object_name in download_objects(signer, namespace, src_bucket):
            object_names.append(object_name)
        upload_objects(signer, namespace, remote_host, remote_path, object_names, remote_user, local_path)
        delete_objects(signer, namespace, src_bucket, object_names)
        delete_local_files(local_path, object_names)
    except (Exception, ValueError) as ex:
        logging.error(str(ex))
 
    return response.Response(
        ctx, 
        response_data=json.dumps(resp),
        headers={"Content-Type": "application/json"}
    )
