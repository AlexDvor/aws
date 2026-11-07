resource "aws_cloudwatch_log_group" "app" {
  name              = "/${var.project}/app"
  retention_in_days = 7
}

resource "aws_sns_topic" "alerts" {
  name = "${var.project}-alerts"
}

data "aws_caller_identity" "current" {}

resource "aws_sns_topic_policy" "alerts" {
  arn = aws_sns_topic.alerts.arn
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "CloudWatchAlarms", Effect = "Allow"
      Principal = { Service = "cloudwatch.amazonaws.com" }
      Action    = "sns:Publish", Resource = aws_sns_topic.alerts.arn
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
        ArnLike      = { "aws:SourceArn" = "arn:aws:cloudwatch:${var.aws_region}:${data.aws_caller_identity.current.account_id}:alarm:${var.project}-*" }
      }
    }]
  })
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.notification_email
}

locals {
  alarms = {
    unhealthy = {
      metric     = "UnHealthyHostCount", statistic = "Maximum", threshold = 1
      comparison = "GreaterThanOrEqualToThreshold", missing = "breaching"
    }
    errors = {
      metric     = "HTTPCode_Target_5XX_Count", statistic = "Sum", threshold = 5
      comparison = "GreaterThanOrEqualToThreshold", missing = "notBreaching"
    }
    capacity = {
      metric     = "HealthyHostCount", statistic = "Minimum", threshold = 2
      comparison = "LessThanThreshold", missing = "breaching"
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "app" {
  for_each            = local.alarms
  alarm_name          = "${var.project}-${each.key}"
  alarm_description   = "Lab threshold; review with actual workload measurements."
  namespace           = "AWS/ApplicationELB"
  metric_name         = each.value.metric
  statistic           = each.value.statistic
  comparison_operator = each.value.comparison
  threshold           = each.value.threshold
  evaluation_periods  = 2
  period              = 60
  treat_missing_data  = each.value.missing
  dimensions = {
    LoadBalancer = aws_lb.app.arn_suffix
    TargetGroup  = aws_lb_target_group.app.arn_suffix
  }
  alarm_actions = [aws_sns_topic.alerts.arn]
  ok_actions    = [aws_sns_topic.alerts.arn]
  depends_on    = [aws_sns_topic_policy.alerts]
}

resource "aws_cloudwatch_dashboard" "app" {
  dashboard_name = "${var.project}-overview"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6
        properties = {
          title = "ALB requests and target errors", region = var.aws_region, period = 60, stat = "Sum"
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", aws_lb.app.arn_suffix],
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", aws_lb.app.arn_suffix]
          ]
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6
        properties = {
          title = "EC2 CPU and ASG capacity", region = var.aws_region, period = 60, stat = "Average"
          metrics = [
            ["AWS/EC2", "CPUUtilization", "AutoScalingGroupName", aws_autoscaling_group.app.name],
            ["AWS/AutoScaling", "GroupInServiceInstances", "AutoScalingGroupName", aws_autoscaling_group.app.name, { yAxis = "right" }]
          ]
        }
      }
    ]
  })
}

resource "aws_budgets_budget" "monthly" {
  name         = "${var.project}-account-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  # Account-wide by design: no dependency on activated cost allocation tags.
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.notification_email]
  }
  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 100
    threshold_type             = "PERCENTAGE"
    notification_type          = "FORECASTED"
    subscriber_email_addresses = [var.notification_email]
  }
}
