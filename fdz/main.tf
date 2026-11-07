data "aws_ssm_parameter" "ami" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_dynamodb_table" "visits" {
  name         = "${var.project}-visits"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "id"
  attribute {
    name = "id"
    type = "S"
  }
  server_side_encryption {
    enabled = true
  }
  point_in_time_recovery {
    enabled = true
  }
}

resource "aws_iam_role" "app" {
  name_prefix = "${var.project}-ec2-"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "ec2.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "app" {
  role = aws_iam_role.app.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow", Action = ["dynamodb:UpdateItem", "dynamodb:DescribeTable"]
        Resource = aws_dynamodb_table.visits.arn
      },
      {
        Effect   = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
        Resource = "${aws_cloudwatch_log_group.app.arn}:*"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "app" {
  name_prefix = "${var.project}-"
  role        = aws_iam_role.app.name
}

resource "aws_lb" "app" {
  name                       = "${var.project}-alb"
  load_balancer_type         = "application"
  internal                   = false
  subnets                    = aws_subnet.public[*].id
  security_groups            = [aws_security_group.alb.id]
  drop_invalid_header_fields = true
}

resource "aws_lb_target_group" "app" {
  name                 = "${var.project}-app"
  port                 = 8080
  protocol             = "HTTP"
  vpc_id               = aws_vpc.main.id
  deregistration_delay = 30
  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 30
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

resource "aws_launch_template" "app" {
  name_prefix            = "${var.project}-"
  image_id               = data.aws_ssm_parameter.ami.value
  instance_type          = var.instance_type
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile {
    name = aws_iam_instance_profile.app.name
  }
  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }
  monitoring {
    enabled = true
  }
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_type           = "gp3"
      volume_size           = 8
      encrypted             = true
      delete_on_termination = true
    }
  }
  user_data = base64encode(templatefile("${path.module}/user_data.sh.tftpl", {
    app_base64 = filebase64("${path.module}/app.py")
    region     = var.aws_region
    table      = aws_dynamodb_table.visits.name
    log_group  = aws_cloudwatch_log_group.app.name
  }))
  tag_specifications {
    resource_type = "instance"
    tags          = { Name = "${var.project}-app", Project = var.project }
  }
}

resource "aws_autoscaling_group" "app" {
  name_prefix               = "${var.project}-"
  min_size                  = 2
  desired_capacity          = 2
  max_size                  = 4
  vpc_zone_identifier       = aws_subnet.private[*].id
  target_group_arns         = [aws_lb_target_group.app.arn]
  health_check_type         = "ELB"
  health_check_grace_period = 600
  default_instance_warmup   = 300
  launch_template {
    id      = aws_launch_template.app.id
    version = aws_launch_template.app.latest_version
  }
  instance_refresh {
    strategy = "Rolling"
    preferences {
      min_healthy_percentage = 100
      max_healthy_percentage = 150
      instance_warmup        = 300
    }
  }
  enabled_metrics = ["GroupDesiredCapacity", "GroupInServiceInstances", "GroupTotalInstances"]
  lifecycle {
    ignore_changes = [desired_capacity]
  }
  depends_on = [
    aws_route.nat, aws_route_table_association.private, aws_vpc_endpoint.dynamodb,
    aws_iam_role_policy.app, aws_lb_listener.http,
    aws_vpc_security_group_egress_rule.https, aws_vpc_security_group_ingress_rule.app,
    aws_vpc_security_group_egress_rule.alb_app
  ]
}

resource "aws_autoscaling_policy" "requests" {
  name                   = "${var.project}-requests"
  autoscaling_group_name = aws_autoscaling_group.app.name
  policy_type            = "TargetTrackingScaling"
  target_tracking_configuration {
    # Lab tuning value, not a measured capacity or production SLO.
    target_value = 300
    predefined_metric_specification {
      predefined_metric_type = "ALBRequestCountPerTarget"
      resource_label         = "${aws_lb.app.arn_suffix}/${aws_lb_target_group.app.arn_suffix}"
    }
  }
}
