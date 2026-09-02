variable "region" {
  description = "Região AWS"
  type        = string
  default     = "us-east-1"
}

variable "project" {
  description = "Prefixo de nomes dos recursos"
  type        = string
  default     = "nexa"
}

variable "environment" {
  description = "Ambiente (production/staging)"
  type        = string
  default     = "production"
}

## Aplicação ---------------------------------------------------------------
variable "image" {
  description = "Imagem da API em ECR (ex.: <conta>.dkr.ecr.us-east-1.amazonaws.com/nexa-api:latest). Vazio = usa ECR criado por este Terraform."
  type        = string
  default     = ""
}

variable "image_tag" {
  description = "Tag usada quando `image` estiver vazio"
  type        = string
  default     = "latest"
}

variable "site_url" {
  description = "URL pública (ex.: https://nexa.example.com). Vazio = usa o DNS do ALB."
  type        = string
  default     = ""
}

variable "acm_certificate_arn" {
  description = "ARN de certificado ACM para o listener HTTPS. Vazio = ALB só em HTTP."
  type        = string
  default     = ""
}

variable "route53_zone_id" {
  description = "Zona Route53 para criar o registro A (apenas se `site_url` for preenchido)."
  type        = string
  default     = ""
}

variable "allowed_ingress_cidrs" {
  description = "CIDRs permitidos no ALB"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "ecs_cpu" {
  description = "Unidades de CPU da task Fargate (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "ecs_memory" {
  description = "Memória da task Fargate (MB)"
  type        = number
  default     = 1024
}

variable "desired_count" {
  description = "Réplicas iniciais do serviço"
  type        = number
  default     = 1
}

variable "max_capacity" {
  description = "Réplicas máximas com autoscaling (0 desliga)"
  type        = number
  default     = 2
}

variable "allow_registration" {
  type    = string
  default = "true"
}

variable "max_upload_mb" {
  type    = string
  default = "25"
}

## Banco -------------------------------------------------------------------
variable "db_instance_class" {
  description = "Tipo de instância RDS"
  type        = string
  default     = "db.t4g.small"
}

variable "db_allocated_storage" {
  type    = number
  default = 20
}

variable "db_name" {
  type    = string
  default = "nexa"
}

## Redis -------------------------------------------------------------------
variable "redis_node_type" {
  description = "Tipo de nó do ElastiCache"
  type        = string
  default     = "cache.t4g.micro"
}