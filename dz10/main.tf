data "aws_elastic_beanstalk_solution_stack" "python" {
  most_recent = true
  name_regex  = "^64bit Amazon Linux 2023 .* running Python 3\\.13$"
}

resource "aws_iam_role" "service" {
  name = "my-app-elasticbeanstalk-service-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "elasticbeanstalk.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "service_health" {
  role       = aws_iam_role.service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSElasticBeanstalkEnhancedHealth"
}

resource "aws_iam_role" "ec2" {
  name = "aws-elasticbeanstalk-ec2-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "web_tier" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AWSElasticBeanstalkWebTier"
}

resource "aws_iam_instance_profile" "ec2" {
  name = "aws-elasticbeanstalk-ec2-role"
  role = aws_iam_role.ec2.name
}

resource "aws_elastic_beanstalk_application" "app" {
  name = "my-app"
}

resource "aws_elastic_beanstalk_environment" "app" {
  name                = "my-app-env"
  application         = aws_elastic_beanstalk_application.app.name
  solution_stack_name = data.aws_elastic_beanstalk_solution_stack.python.name
  tier                = "WebServer"

  # Without version_label, AWS deploys its platform Sample application.
  setting {
    namespace = "aws:elasticbeanstalk:environment"
    name      = "EnvironmentType"
    value     = "SingleInstance"
  }

  setting {
    namespace = "aws:ec2:instances"
    name      = "InstanceTypes"
    value     = "t3.micro"
  }

  setting {
    namespace = "aws:autoscaling:launchconfiguration"
    name      = "IamInstanceProfile"
    value     = aws_iam_instance_profile.ec2.name
  }

  setting {
    namespace = "aws:elasticbeanstalk:environment"
    name      = "ServiceRole"
    value     = aws_iam_role.service.arn
  }

  setting {
    namespace = "aws:elasticbeanstalk:healthreporting:system"
    name      = "SystemType"
    value     = "enhanced"
  }

  depends_on = [
    aws_iam_role_policy_attachment.service_health,
    aws_iam_role_policy_attachment.web_tier,
  ]
}
