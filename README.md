
# Download and Transfer

OCI Function that pulls objects from a bucket and pushes them to a remote host and the deletes the object from the bucket.

This function uses Resource Principals to securely authorize a function to make API calls to OCI services using the OCI Python SDK.

The function calls the following OCI Python SDK classes:

[Resource Principals Signer](https://oracle-cloud-infrastructure-python-sdk.readthedocs.io/en/latest/api/signing.html#resource-principals-signer) to authenticate.

[Object Storage Client](https://oracle-cloud-infrastructure-python-sdk.readthedocs.io/en/latest/api/object_storage/client/oci.object_storage.ObjectStorageClient.html) to interact with Object Storage.






## Initial Configuration

To follow along make sure you have your tenancy created in OCI and docker installed.

### Create OCI Group and OCI user, Assign the user to this group. Give the following privileges via policy to group

```policy
Allow group oci_group to manage repos in tenancy
allow group oci_group to manage objects in tenancy
allow group oci_group to use repos in tenancy
allow group oci_group to read repos in tenancy
allow group oci_group to use keys in compartment sandbox
allow group oci_group to read objectstorage-namespaces in compartment sandbox
Allow group oci_group to manage all-resources in tenancy
```

Also generate an AUTH token for us to use the user to login via docker cli

### Create a Dynamic group for function and the following matching rule

```bash
ALL {resource.type = 'fnfunc', resource.compartment.id = 'ocid1.tenancy.oc1...'}
```

### Create a policy for the Dynamic Group

```bash
Allow service objectstorage-us-ashburn-1 to manage object-family in compartment sandbox
Allow dynamic-group function-dynamic-group to manage objects in compartment sandbox
Allow dynamic-group function-dynamic-group to manage buckets in compartment sandbox
Allow dynamic-group function-dynamic-group to manage secret-family in tenancy
```

### Configure Docker login to OCI Registry

```bash
docker login us-ashburn-1.ocir.io -u '<namespace>/<username>' -p '<auth token>'
```

### Install Fn CLI

```bash

curl -LSs https://raw.githubusercontent.com/fnproject/cli/master/install | sh
```

```bash
fn version
```

### Create and Configure Fn context 

```bash
fn create context ocir-context --provider oracle
fn update context registry us-ashburn-1.ocir.io/<namespace>/download_and_transfer
fn update context oracle.compartment-id <tenancy_ocid>
fn update context api-url https://functions.us-ashburn-1.oraclecloud.com
```

In my case i've used us-ashburn-1 as my region key. Also make sure that the region key in both docker login and fn context is same. Fn uses docker login to push and pull images from OCI registry

```bash
(dntv4) ubuntu@dockervm:$ fn use context ocir-context
(dntv4) ubuntu@dockervm:$ fn list context
CURRENT	NAME		PROVIDER	API URL					        REGISTRY
	default		default         http://localhost:8080			        iad.ocir.io/<namespace>/dnt
*	ocir-context	oracle		https://functions.us-ashburn-1.oraclecloud.com	us-ashburn-1.ocir.io/<namespace>/download_and_transfer
```

### Store private key to connect to remote host in oracle vault secret

This can be done via OCI Dashboard
## Deployment

To deploy this project we will create an application 

```bash
fn create app download_and_transfer --annotation oracle.com/oci/subnetIds='["ocid1.subnet.oc1.iad...."]'
```

Build and push the image to OCI registry

```bash
fn --verbose deploy --app download_and_transfer
```

### Update configuration

Update the SECRET_OCID configuration of function with the ocid of secret created earlier.

![Create Secret](https://github.com/nitin23c/oci_function_example/assets/11648754/185af46f-84be-46d2-825d-233c633c4869)

To test the build , Enable emit events of a bucket.

### Create an event with following rule 

![Event Rule with Bucket Attributes](https://github.com/nitin23c/oci_function_example/assets/11648754/fc4f58dc-b571-4d41-94f5-cf7a5ccfa31c)

### Add action in the same event to trigger oci_function_example

![Event Action](https://github.com/nitin23c/oci_function_example/assets/11648754/1fe65d94-1601-4e48-87ed-28172650b059)

At this point you can upload the objects to the bucket which should invoke the function and the function should pull the objects from the bucket transfers it to remote host and delete the object from the bucket.
