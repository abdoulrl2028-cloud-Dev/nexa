locals {
  prefix        = "${var.project}-${var.environment}"
  vpc_cidr      = "10.0.0.0/16"
  azs           = data.aws_availability_zones.available.names
  public_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_cidrs = ["10.0.10.0/24", "10.0.11.0/24"]
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "nexa" {
  cidr_block           = local.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = { Name = "${local.prefix}-vpc" }
}

resource "aws_internet_gateway" "nexa" {
  vpc_id = aws_vpc.nexa.id
  tags   = { Name = "${local.prefix}-igw" }
}

# Sub-redes públicas (ALB) + NAT
resource "aws_subnet" "public" {
  count                   = length(local.public_cidrs)
  vpc_id                  = aws_vpc.nexa.id
  cidr_block              = local.public_cidrs[count.index]
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true
  tags                    = { Name = "${local.prefix}-public-${count.index}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.nexa.id
  tags   = { Name = "${local.prefix}-rt-public" }
}

resource "aws_route" "public_default" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.nexa.id
}

resource "aws_route_table_association" "public" {
  count          = length(local.public_cidrs)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_eip" "nat" {
  count  = length(local.public_cidrs)
  domain = "vpc"
  tags   = { Name = "${local.prefix}-nat-eip-${count.index}" }
}

resource "aws_nat_gateway" "nexa" {
  count         = length(local.public_cidrs)
  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[count.index].id
  tags          = { Name = "${local.prefix}-nat-${count.index}" }
}

# Sub-redes privadas (ECS, RDS, Redis)
resource "aws_subnet" "private" {
  count             = length(local.private_cidrs)
  vpc_id            = aws_vpc.nexa.id
  cidr_block        = local.private_cidrs[count.index]
  availability_zone = local.azs[count.index]
  tags              = { Name = "${local.prefix}-private-${count.index}" }
}

resource "aws_route_table" "private" {
  count  = length(local.private_cidrs)
  vpc_id = aws_vpc.nexa.id
  tags   = { Name = "${local.prefix}-rt-private-${count.index}" }
}

resource "aws_route" "private_default" {
  count                  = length(local.private_cidrs)
  route_table_id         = aws_route_table.private[count.index].id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.nexa[count.index].id
}

resource "aws_route_table_association" "private" {
  count          = length(local.private_cidrs)
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

resource "aws_security_group" "alb" {
  name        = "${local.prefix}-alb"
  vpc_id      = aws_vpc.nexa.id
  description = "Entrada HTTP(S) para o load balancer"

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = var.allowed_ingress_cidrs
  }
  dynamic "ingress" {
    for_each = var.acm_certificate_arn != "" ? [1] : []
    content {
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = var.allowed_ingress_cidrs
    }
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${local.prefix}-alb" }
}

resource "aws_security_group" "ecs" {
  name        = "${local.prefix}-ecs"
  vpc_id      = aws_vpc.nexa.id
  description = "Tráfego da app a partir do ALB"

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "${local.prefix}-ecs" }
}

resource "aws_security_group" "db" {
  name        = "${local.prefix}-db"
  vpc_id      = aws_vpc.nexa.id
  description = "PostgreSQL só para a app"

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }
  tags = { Name = "${local.prefix}-db" }
}

resource "aws_security_group" "redis" {
  name        = "${local.prefix}-redis"
  vpc_id      = aws_vpc.nexa.id
  description = "Redis só para a app"

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }
  tags = { Name = "${local.prefix}-redis" }
}