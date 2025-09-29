########################################
# Inputs & identity
########################################
variable "aws_region" {
  type    = string
  default = "us-east-2" # set your region
}

data "aws_caller_identity" "current" {}

locals {
  membox_ctx    = "../membox"
  registry_host = "${data.aws_caller_identity.current.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
}

########################################
# ECR repositories (declare them here!)
########################################
resource "aws_ecr_repository" "api" {
  name                 = "tts_api"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_ecr_repository" "cleanup" {
  name                 = "lambda_cleanup"
  image_tag_mutability = "MUTABLE"
  force_delete         = true
  image_scanning_configuration { scan_on_push = true }
}

# resource "null_resource" "docker_login" {
#   provisioner "local-exec" {
#     command = <<EOC
# set -euo pipefail
# aws ecr get-login-password --region ${var.aws_region} \
#   | docker login --username AWS --password-stdin ${local.registry_host}
# EOC
#   }
# }

########################################
# Build & push: API image (Dockerfile.api)
########################################
resource "null_resource" "image_api" {
  triggers = {
    hash = md5(join("-", [
      for f in concat(
        tolist(fileset(local.membox_ctx, "**/*.py")),
        tolist(fileset(local.membox_ctx, "**/*.txt")),
        tolist(fileset(local.membox_ctx, "Dockerfile.api"))
      ) : filemd5("${local.membox_ctx}/${f}")
    ]))
  }

  provisioner "local-exec" {
    command = <<EOF
set -euo pipefail
aws ecr get-login-password --region ${var.aws_region} \
  | docker login --username AWS --password-stdin ${local.registry_host}
docker build --platform linux/amd64 \
  -f ${local.membox_ctx}/Dockerfile.api \
  -t ${aws_ecr_repository.api.repository_url}:latest \
  ${local.membox_ctx}
docker push ${aws_ecr_repository.api.repository_url}:latest
EOF
  }
}

data "aws_ecr_image" "api_latest" {
  repository_name = aws_ecr_repository.api.name
  image_tag       = "latest"
  depends_on      = [null_resource.image_api]
}

########################################
# Build & push: CLEANUP image (Dockerfile.cleanup)
########################################
resource "null_resource" "image_cleanup" {
  triggers = {
    hash = md5(join("-", [
      for f in concat(
        tolist(fileset(local.membox_ctx, "**/*.py")),
        tolist(fileset(local.membox_ctx, "**/*.txt")),
        tolist(fileset(local.membox_ctx, "Dockerfile.cleanup"))
      ) : filemd5("${local.membox_ctx}/${f}")
    ]))
  }

  provisioner "local-exec" {
    command = <<EOF
set -euo pipefail
aws ecr get-login-password --region ${var.aws_region} \
  | docker login --username AWS --password-stdin ${local.registry_host}
docker build --platform linux/amd64 \
  -f ${local.membox_ctx}/Dockerfile.cleanup \
  -t ${aws_ecr_repository.cleanup.repository_url}:latest \
  ${local.membox_ctx}
docker push ${aws_ecr_repository.cleanup.repository_url}:latest
EOF
  }
}

data "aws_ecr_image" "cleanup_latest" {
  repository_name = aws_ecr_repository.cleanup.name
  image_tag       = "latest"
  depends_on      = [null_resource.image_cleanup]
}
