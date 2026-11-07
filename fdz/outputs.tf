output "application_url" {
  value = "http://${aws_lb.app.dns_name}"
}

output "autoscaling_group_name" {
  value = aws_autoscaling_group.app.name
}

output "dynamodb_table" {
  value = aws_dynamodb_table.visits.name
}

output "cloudwatch_dashboard" {
  value = "https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.app.dashboard_name}"
}

output "log_group" {
  value = aws_cloudwatch_log_group.app.name
}

output "budget_name" {
  value = aws_budgets_budget.monthly.name
}
