data "aws_partition" "current" {}

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_vpc" "lab" {
  cidr_block           = "10.99.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "dz9" }
}

resource "aws_subnet" "lab" {
  vpc_id     = aws_vpc.lab.id
  cidr_block = "10.99.1.0/24"
}

resource "aws_internet_gateway" "lab" {
  vpc_id = aws_vpc.lab.id
}

resource "aws_route_table" "lab" {
  vpc_id = aws_vpc.lab.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.lab.id
  }
}

resource "aws_route_table_association" "lab" {
  subnet_id      = aws_subnet.lab.id
  route_table_id = aws_route_table.lab.id
}

resource "aws_security_group" "lab" {
  name_prefix = "dz9-"
  description = "No inbound access; outbound for packages, SSM and CloudWatch"
  vpc_id      = aws_vpc.lab.id
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_iam_role" "lab" {
  name_prefix = "dz9-ec2-"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lab" {
  for_each   = toset(["CloudWatchAgentServerPolicy", "AmazonSSMManagedInstanceCore"])
  role       = aws_iam_role.lab.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/${each.value}"
}

resource "aws_iam_instance_profile" "lab" {
  name_prefix = "dz9-"
  role        = aws_iam_role.lab.name
}

resource "aws_instance" "lab" {
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = "t3.micro"
  subnet_id                   = aws_subnet.lab.id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.lab.id]
  iam_instance_profile        = aws_iam_instance_profile.lab.name
  monitoring                  = true
  user_data_replace_on_change = true
  user_data                   = file("${path.module}/user-data.sh")

  metadata_options {
    http_tokens = "required"
  }
  root_block_device {
    volume_type = "gp3"
    volume_size = 8
    encrypted   = true
  }
  tags       = { Name = "dz9-cloudwatch" }
  depends_on = [aws_route_table_association.lab, aws_iam_role_policy_attachment.lab]
}

resource "aws_sns_topic" "alerts" {
  name_prefix = "dz9-alerts-"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.notification_email
}

locals {
  alarms = {
    cpu    = { namespace = "AWS/EC2", metric = "CPUUtilization", threshold = 80 }
    memory = { namespace = "CWAgent", metric = "mem_used_percent", threshold = 75 }
  }
}

resource "aws_cloudwatch_metric_alarm" "usage" {
  for_each            = local.alarms
  alarm_name          = "dz9-${aws_instance.lab.id}-${each.key}-high"
  alarm_description   = "${each.value.metric} > ${each.value.threshold}% for 5 consecutive one-minute periods"
  namespace           = each.value.namespace
  metric_name         = each.value.metric
  dimensions          = { InstanceId = aws_instance.lab.id }
  comparison_operator = "GreaterThanThreshold"
  threshold           = each.value.threshold
  statistic           = "Average"
  period              = 60
  evaluation_periods  = 5
  datapoints_to_alarm = 5
  treat_missing_data  = "missing"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_dashboard" "lab" {
  dashboard_name = "dz9-${aws_instance.lab.id}"
  dashboard_body = jsonencode({
    widgets = [{
      type = "metric", x = 0, y = 0, width = 24, height = 8
      properties = {
        title  = "EC2 CPU and memory (%)"
        region = var.aws_region, view = "timeSeries", stat = "Average", period = 60
        metrics = [
          ["AWS/EC2", "CPUUtilization", "InstanceId", aws_instance.lab.id],
          ["CWAgent", "mem_used_percent", "InstanceId", aws_instance.lab.id]
        ]
        yAxis = { left = { min = 0, max = 100 } }
      }
    }]
  })
}
