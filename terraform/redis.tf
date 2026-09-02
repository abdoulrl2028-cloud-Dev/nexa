resource "aws_elasticache_subnet_group" "nexa" {
  name       = "${local.prefix}-redis-subnet"
  subnet_ids = aws_subnet.private[*].id
}

# Redis simples (1 nó, sem TLS: acesso restrito ao SG da app, que é privada).
resource "aws_elasticache_cluster" "nexa" {
  cluster_id           = "${local.prefix}-redis"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.redis_node_type
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.nexa.name
  security_group_ids = [aws_security_group.redis.id]

  tags = { Name = "${local.prefix}-redis" }
}