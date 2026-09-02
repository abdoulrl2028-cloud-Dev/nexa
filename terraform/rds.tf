resource "aws_db_subnet_group" "nexa" {
  name       = "${local.prefix}-db-subnet"
  subnet_ids = aws_subnet.private[*].id
  tags       = { Name = "${local.prefix}-db-subnet" }
}

resource "random_password" "db_password" {
  length  = 24
  special = false
}

resource "aws_db_instance" "nexa" {
  identifier = "${local.prefix}-db"

  engine                = "postgres"
  engine_version        = "16.3"
  instance_class        = var.db_instance_class
  allocated_storage     = var.db_allocated_storage
  max_allocated_storage = var.db_allocated_storage * 2

  db_name  = var.db_name
  username = "nexa"
  password = random_password.db_password.result

  db_subnet_group_name    = aws_db_subnet_group.nexa.name
  vpc_security_group_ids  = [aws_security_group.db.id]
  multi_az                = false
  publicly_accessible     = false
  skip_final_snapshot     = false
  backup_retention_period = 7

  tags = { Name = "${local.prefix}-db" }
}