output "alb_dns" {
  description = "URL de acesso público (DNS do load balancer)"
  value       = var.site_url != "" ? var.site_url : aws_lb.nexa.dns_name
}

output "site_url" {
  value = local.site_host
}

output "database_endpoint" {
  value = aws_db_instance.nexa.endpoint
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.nexa.cache_nodes[0].address
}

output "media_bucket" {
  value = aws_s3_bucket.media.id
}

output "ecr_repository_url" {
  value = aws_ecr_repository.nexa.repository_url
}

output "ecs_cluster" {
  value = aws_ecs_cluster.nexa.name
}

output "ecs_service" {
  value = aws_ecs_service.nexa.name
}