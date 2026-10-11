variable "aws_region" {
  type    = string
  default = "eu-central-1"
}
variable "project_name" {
  type    = string
  default = "nginx-lab"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,19}$", var.project_name))
    error_message = "Use 3-20 lowercase letters, digits or hyphens, starting with a letter."
  }
}
variable "public_key_path" {
  description = "Local public key file; the private key never enters Terraform."
  type        = string
  default     = ".keys/nginx-lab.pub"
}
variable "allowed_http_cidr" {
  description = "Your public IPv4/32 for browser HTTP access."
  type        = string
  validation {
    condition     = can(cidrnetmask(var.allowed_http_cidr)) && !endswith(var.allowed_http_cidr, "/0")
    error_message = "Provide an IPv4 CIDR, preferably your IP/32; /0 is forbidden."
  }
}
variable "install_nginx_automatically" {
  description = "Set false to install nginx manually via EC2 Instance Connect."
  type        = bool
  default     = true
}
