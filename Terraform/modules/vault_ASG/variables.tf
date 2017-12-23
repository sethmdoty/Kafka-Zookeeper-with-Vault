variable "ready" {

}

variable "management_sg_id"{
}

variable "system_role_arn"{
}

# ---------------------------------------------------------------------------------------------------------------------
# REQUIRED PARAMETERS
# ---------------------------------------------------------------------------------------------------------------------

variable "subnets" {
  description = "List of subnet IDs configured for Vault servers."
  type = "list"
}

variable "region" {
  description = "AWS region"
}

variable "access_key" {
}

variable "secret_key" {
}

variable "ami_id" {
  description = "The ID of the AMI to run in the cluster. This should be an AMI built from the Packer template under examples/vault-consul-ami/vault-consul.json. If no AMI is specified, the template will 'just work' by using the example public AMIs. WARNING! Do not use the example AMIs in a production setting!"
  default = ""
}

# ---------------------------------------------------------------------------------------------------------------------
# OPTIONAL PARAMETERS
# These parameters have reasonable defaults.
# ---------------------------------------------------------------------------------------------------------------------

variable "force_destroy_s3_bucket" {
  description = "If you set this to true, when you run terraform destroy, this tells Terraform to delete all the objects in the S3 bucket used for backend storage. You should NOT set this to true in production or you risk losing all your data! This property is only here so automated tests of this module can clean up after themselves."
  default     = false
}

variable "s3_bucket_name" {
  description = "The name of the S3 bucket to create and use as a storage backend."
  default = "vault-storage-backend-bucket"
}

variable "cluster_name" {
  description = "The name of the Vault cluster (e.g. vault-stage). This variable is used to namespace all resources created by this module."
  default = "vault-cluster"
}

variable "vault_cluster_name" {
  description = "What to name the Vault server cluster and all of its associated resources"
  default     = "vault-cluster"
}

variable "consul_cluster_name" {
  description = "What to name the Consul server cluster and all of its associated resources"
  default     = "consul-cluster"
}

variable "consul_cluster_tag_key" {
  description = "The tag the Consul EC2 Instances will look for to automatically discover each other and form a cluster."
  default     = "consul-servers"
}
