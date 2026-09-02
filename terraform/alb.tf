locals {
  site_host = (
    var.site_url != "" ? var.site_url :
    (var.acm_certificate_arn != "" ? "https://${aws_lb.nexa.dns_name}" : "http://${aws_lb.nexa.dns_name}")
  )
  www_host = replace(replace(local.site_host, "https://", ""), "http://", "")
  api_host = local.www_host
}

resource "aws_lb" "nexa" {
  name               = "${local.prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  tags               = { Name = "${local.prefix}-alb" }
}

resource "aws_lb_target_group" "nexa" {
  name        = "${local.prefix}-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.nexa.id
  target_type = "ip"
  health_check {
    path                = "/"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 3
    unhealthy_threshold = 3
    matcher             = "200"
  }
  tags = { Name = "${local.prefix}-tg" }
}

# HTTP: ou redireciona para HTTPS (quando há ACM) ou segue direto para a app.
resource "aws_lb_listener" "http_redirect" {
  count             = var.acm_certificate_arn != "" ? 1 : 0
  load_balancer_arn = aws_lb.nexa.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "http_forward" {
  count             = var.acm_certificate_arn == "" ? 1 : 0
  load_balancer_arn = aws_lb.nexa.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.nexa.arn
  }
}

resource "aws_lb_listener" "https" {
  count             = var.acm_certificate_arn != "" ? 1 : 0
  load_balancer_arn = aws_lb.nexa.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.nexa.arn
  }
}

resource "aws_route53_record" "nexa" {
  count   = var.site_url != "" ? 1 : 0
  zone_id = var.route53_zone_id
  name    = local.www_host
  type    = "A"
  alias {
    name                   = aws_lb.nexa.dns_name
    zone_id                = aws_lb.nexa.zone_id
    evaluate_target_health = true
  }
}