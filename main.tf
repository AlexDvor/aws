data "aws_availability_zones" "available" {
  state = "available"
  filter {
    name   = "zone-type"
    values = ["availability-zone"]
  }
}
data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}
data "aws_ec2_managed_prefix_list" "instance_connect" {
  name = "com.amazonaws.${var.aws_region}.ec2-instance-connect"
}
resource "aws_vpc" "lab" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.project_name}-vpc" }
}
resource "aws_internet_gateway" "lab" {
  vpc_id = aws_vpc.lab.id
}
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.lab.id
  cidr_block              = cidrsubnet(aws_vpc.lab.cidr_block, 8, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.project_name}-public-${count.index + 1}" }
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.lab.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.lab.id
  }
}
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}
resource "aws_security_group" "alb" {
  name_prefix = "${var.project_name}-alb-"
  description = "Lab load balancer"
  vpc_id      = aws_vpc.lab.id
}
resource "aws_security_group" "web" {
  name_prefix = "${var.project_name}-web-"
  description = "Lab nginx servers"
  vpc_id      = aws_vpc.lab.id
}
resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = var.allowed_http_cidr
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
}
resource "aws_vpc_security_group_egress_rule" "alb_to_web" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.web.id
  ip_protocol                  = "tcp"
  from_port                    = 80
  to_port                      = 80
}
resource "aws_vpc_security_group_ingress_rule" "web_from_alb" {
  security_group_id            = aws_security_group.web.id
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = 80
  to_port                      = 80
}
resource "aws_vpc_security_group_ingress_rule" "web_direct_http" {
  security_group_id = aws_security_group.web.id
  cidr_ipv4         = var.allowed_http_cidr
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
}
resource "aws_vpc_security_group_ingress_rule" "web_console_ssh" {
  security_group_id = aws_security_group.web.id
  prefix_list_id    = data.aws_ec2_managed_prefix_list.instance_connect.id
  ip_protocol       = "tcp"
  from_port         = 22
  to_port           = 22
}
# Package downloads require outbound internet access; no NAT Gateway.
resource "aws_vpc_security_group_egress_rule" "web_outbound" {
  security_group_id = aws_security_group.web.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
resource "aws_key_pair" "lab" {
  key_name   = "${var.project_name}-key"
  public_key = file(pathexpand(var.public_key_path))
}
resource "aws_instance" "web" {
  count                       = 2
  ami                         = data.aws_ssm_parameter.al2023.value
  instance_type               = "t3.micro"
  subnet_id                   = aws_subnet.public[count.index].id
  associate_public_ip_address = true
  vpc_security_group_ids      = [aws_security_group.web.id]
  key_name                    = aws_key_pair.lab.key_name
  user_data                   = var.install_nginx_automatically ? file("${path.module}/user-data.sh") : null
  user_data_replace_on_change = true
  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }
  root_block_device {
    volume_type           = "gp3"
    volume_size           = 8
    encrypted             = true
    delete_on_termination = true
  }
  credit_specification {
    cpu_credits = "standard"
  }
  tags = { Name = "${var.project_name}-web-${count.index + 1}" }
  depends_on = [
    aws_route_table_association.public,
    aws_vpc_security_group_egress_rule.web_outbound
  ]
}
resource "aws_lb" "lab" {
  name                       = "${var.project_name}-alb"
  internal                   = false
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  subnets                    = aws_subnet.public[*].id
  enable_deletion_protection = false
  depends_on                 = [aws_route_table_association.public]
}
resource "aws_lb_target_group" "web" {
  name        = "${var.project_name}-tg"
  port        = 80
  protocol    = "HTTP"
  target_type = "instance"
  vpc_id      = aws_vpc.lab.id
  health_check {
    path    = "/"
    matcher = "200"
  }
}
resource "aws_lb_target_group_attachment" "web" {
  count            = 2
  target_group_arn = aws_lb_target_group.web.arn
  target_id        = aws_instance.web[count.index].id
  port             = 80
}
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.lab.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.web.arn
  }
}
