terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "6.6.0" }
  }
}

provider "aws" {
  profile = "default"
  region  = "us-east-2"
}
locals {
  repos_url = aws_ecr_repository.api.repository_url
}

resource "aws_s3_bucket" "voice_storage" {
  bucket        = "membox-wavs"
  force_destroy = true
}
output "api_url" {
  value = aws_lambda_function_url.api.function_url
}
