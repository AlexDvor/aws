output "application_url" {
  value = "http://${aws_elastic_beanstalk_environment.app.cname}"
}

output "platform" {
  value = data.aws_elastic_beanstalk_solution_stack.python.name
}
