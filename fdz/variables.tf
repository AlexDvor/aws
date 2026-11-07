variable "aws_region" {
  type    = string
  default = "eu-central-1"
}

variable "project" {
  type    = string
  default = "fdz"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,15}$", var.project))
    error_message = "Use 2–16 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "notification_email" {
  description = "Email for SNS confirmation and budget alerts."
  type        = string
  validation {
    condition     = can(regex("^[^ @]+@[^ @]+\\.[^ @]+$", var.notification_email))
    error_message = "Provide a valid notification email."
  }
}

variable "monthly_budget_usd" {
  description = "Account-wide monthly alert budget; does not stop resources."
  type        = number
  validation {
    condition     = var.monthly_budget_usd > 0
    error_message = "Budget must be positive."
  }
}

variable "instance_type" {
  description = "Choose an x86_64 instance compatible with the selected AMI."
  type        = string
  default     = "t3.micro"
}

variable "allowed_http_cidr" {
  description = "Public demo access; restrict to your public IPv4 /32 when possible."
  type        = string
  default     = "0.0.0.0/0"
  validation {
    condition     = can(cidrnetmask(var.allowed_http_cidr))
    error_message = "Provide an IPv4 CIDR."
  }
}
