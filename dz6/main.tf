data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

resource "aws_db_subnet_group" "lab" {
  name        = "${var.db_identifier}-subnets"
  description = "RDS lab in existing default VPC subnets"
  subnet_ids  = data.aws_subnets.default.ids

  lifecycle {
    precondition {
      condition     = length(data.aws_subnets.default.ids) >= 2
      error_message = "The default VPC needs default subnets in at least two Availability Zones."
    }
    precondition {
      condition     = data.aws_vpc.default.enable_dns_support && data.aws_vpc.default.enable_dns_hostnames
      error_message = "The default VPC must have DNS support and DNS hostnames enabled for public RDS access."
    }
  }
}

resource "aws_security_group" "postgres" {
  name_prefix = "${var.db_identifier}-"
  description = "PostgreSQL access from the lab owner IPv4 only"
  vpc_id      = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_ingress_rule" "postgres" {
  security_group_id = aws_security_group.postgres.id
  description       = "PostgreSQL from the owner public IPv4"
  cidr_ipv4         = var.allowed_ipv4_cidr
  ip_protocol       = "tcp"
  from_port         = 5432
  to_port           = 5432
}

# Security groups are stateful; replies to permitted inbound connections do not
# require a broad outbound rule. Existing default VPC networking is not managed here.
resource "aws_db_instance" "postgres" {
  identifier                   = var.db_identifier
  engine                       = "postgres"
  engine_version               = var.engine_version
  instance_class               = "db.t3.micro"
  allocated_storage            = 20
  storage_type                 = "gp2"
  storage_encrypted            = true
  username                     = "postgres"
  manage_master_user_password  = true
  port                         = 5432
  db_subnet_group_name         = aws_db_subnet_group.lab.name
  vpc_security_group_ids       = [aws_security_group.postgres.id]
  publicly_accessible          = true
  multi_az                     = false
  backup_retention_period      = 1
  auto_minor_version_upgrade   = true
  performance_insights_enabled = false
  monitoring_interval          = 0
  copy_tags_to_snapshot        = true

  # Disposable homework database: destroy removes data and automated backups.
  deletion_protection      = false
  skip_final_snapshot      = true
  delete_automated_backups = true

  depends_on = [aws_vpc_security_group_ingress_rule.postgres]
}
