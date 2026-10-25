output "instance_id" {
  value = aws_instance.lab.id
}

output "sns_topic_arn" {
  value = aws_sns_topic.alerts.arn
}

output "alarm_names" {
  value = { for key, alarm in aws_cloudwatch_metric_alarm.usage : key => alarm.alarm_name }
}

output "dashboard_name" {
  value = aws_cloudwatch_dashboard.lab.dashboard_name
}
