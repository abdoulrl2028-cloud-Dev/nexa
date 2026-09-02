resource "aws_ecr_repository" "nexa" {
  name                 = "${var.project}-api"
  image_tag_mutability = "MUTABLE"
  force_delete         = false

  image_scanning_configuration {
    scan_on_push = true
  }
  tags = { Name = "${local.prefix}-api" }
}

locals {
  image_url = var.image != "" ? var.image : "${aws_ecr_repository.nexa.repository_url}:${var.image_tag}"
}