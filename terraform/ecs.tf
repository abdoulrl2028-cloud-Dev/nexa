locals {
  db_password_url = random_password.db_password.result
  database_url    = "postgresql+psycopg://nexa:${local.db_password_url}@${aws_db_instance.nexa.endpoint}/${var.db_name}"
  redis_url       = "redis://${aws_elasticache_cluster.nexa.cache_nodes[0].address}:${aws_elasticache_cluster.nexa.cache_nodes[0].port}/0"
}

resource "random_password" "secret_key" {
  length  = 48
  special = false
}

resource "aws_cloudwatch_log_group" "nexa" {
  name              = "/ecs/${local.prefix}"
  retention_in_days = 14
}

resource "aws_ecs_cluster" "nexa" {
  name = "${local.prefix}-cluster"
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_ecs_task_definition" "nexa" {
  family                   = "${local.prefix}-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_cpu
  memory                   = var.ecs_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name         = "nexa"
      image        = local.image_url
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      environment = [
        { name = "NEXA_ENV", value = var.environment },
        { name = "SITE_URL", value = local.site_host },
        { name = "WWW_HOST", value = local.www_host },
        { name = "API_HOST", value = local.api_host },
        { name = "SECRET_KEY", value = random_password.secret_key.result },
        { name = "DATABASE_URL", value = local.database_url },
        { name = "REDIS_URL", value = local.redis_url },
        { name = "STORAGE_DRIVER", value = "s3" },
        { name = "S3_BUCKET", value = aws_s3_bucket.media.id },
        { name = "S3_REGION", value = data.aws_region.current.name },
        { name = "ALLOW_REGISTRATION", value = var.allow_registration },
        { name = "MAX_UPLOAD_MB", value = var.max_upload_mb },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.nexa.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "nexa"
        }
      }
    }
  ])

  tags = { Name = "${local.prefix}-task" }
}

resource "aws_ecs_cluster_capacity_providers" "nexa" {
  cluster_name       = aws_ecs_cluster.nexa.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]
  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

resource "aws_ecs_service" "nexa" {
  name            = "${local.prefix}-service"
  cluster         = aws_ecs_cluster.nexa.id
  task_definition = aws_ecs_task_definition.nexa.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.nexa.arn
    container_name   = "nexa"
    container_port   = 8000
  }

  force_new_deployment = true

  depends_on = [aws_lb_listener.http_forward, aws_lb_listener.http_redirect, aws_lb_listener.https]

  tags = { Name = "${local.prefix}-service" }
}

# Autoscaling simples (CPU) se max_capacity > desired_count
resource "aws_appautoscaling_target" "nexa" {
  count              = var.max_capacity > var.desired_count ? 1 : 0
  min_capacity       = var.desired_count
  max_capacity       = var.max_capacity
  resource_id        = "service/${aws_ecs_cluster.nexa.name}/${aws_ecs_service.nexa.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "nexa_cpu" {
  count              = var.max_capacity > var.desired_count ? 1 : 0
  name               = "${local.prefix}-cpu"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.nexa[0].resource_id
  scalable_dimension = aws_appautoscaling_target.nexa[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.nexa[0].service_namespace
  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70
    scale_in_cooldown  = 120
    scale_out_cooldown = 60
  }
}