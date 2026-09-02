terraform {
  backend "s3" {
    # ALTERE para o bucket do seu estado ou remova este bloco para usar estado local.
    # bucket         = "nexa-terraform-state"
    # key            = "nexa/terraform.tfstate"
    # region         = "us-east-1"
    # dynamodb_table = "nexa-terraform-locks"
  }
}

provider "aws" {
  region = var.region
}

provider "random" {}

data "aws_region" "current" {}
data "aws_caller_identity" "current" {}