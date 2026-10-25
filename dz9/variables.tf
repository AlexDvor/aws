variable "aws_region" {
  type    = string
  default = "eu-south-2"
}

variable "notification_email" {
  description = "Email for SNS; confirm the subscription manually after apply."
  type        = string
  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.notification_email))
    error_message = "Provide a valid notification email address."
  }
}
