output "alb_url" {
  value = "http://${aws_lb.lab.dns_name}"
}
output "instances" {
  value = [for instance in aws_instance.web : {
    id         = instance.id
    public_dns = instance.public_dns
    url        = "http://${instance.public_dns}"
  }]
}
output "target_group_arn" {
  value = aws_lb_target_group.web.arn
}
