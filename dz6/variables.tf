variable "aws_region" {
  description = "AWS region containing the default VPC."
  type        = string
  default     = "eu-central-1"
}

variable "db_identifier" {
  description = "Unique RDS identifier within the account and region."
  type        = string
  default     = "dz6-postgres"
  validation {
    condition = (
      can(regex("^[a-z][a-z0-9-]{0,61}[a-z0-9]$", var.db_identifier)) &&
      !strcontains(var.db_identifier, "--")
    )
    error_message = "Use 2-63 lowercase letters, digits or hyphens; start with a letter, do not end with a hyphen or use consecutive hyphens."
  }
}

variable "allowed_ipv4_cidr" {
  description = "Your current public IPv4 address with /32; only this host may connect."
  type        = string
  validation {
    condition = (
      can(cidrnetmask(var.allowed_ipv4_cidr)) &&
      endswith(var.allowed_ipv4_cidr, "/32")
    )
    error_message = "Provide a valid public IPv4 CIDR with /32, e.g. 203.0.113.10/32; replace the example with your actual IP."
  }
}

variable "engine_version" {
  description = "Optional supported PostgreSQL version; null lets RDS select its regional default."
  type        = string
  default     = null
}
