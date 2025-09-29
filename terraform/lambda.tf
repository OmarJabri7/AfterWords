resource "aws_iam_role" "lambda_api" {
  name = "lambda_api"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "lambda.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_api_logs" {
  role       = aws_iam_role.lambda_api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# S3 object-level for your voice bucket (adjust as needed)
resource "aws_iam_policy" "lambda_api_s3" {
  name = "lambda_api_s3_access"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect   = "Allow",
      Action   = ["s3:GetObject", "s3:PutObject"],
      Resource = ["${aws_s3_bucket.voice_storage.arn}/*"]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_api_s3_attach" {
  role       = aws_iam_role.lambda_api.name
  policy_arn = aws_iam_policy.lambda_api_s3.arn
}

resource "aws_iam_role" "lambda_cleanup" {
  name = "lambda_cleanup"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17",
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "lambda.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_cleanup_logs" {
  role       = aws_iam_role.lambda_cleanup.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "lambda_cleanup_ddb_doc" {
  statement {
    actions = [
      "dynamodb:GetItem",
      "dynamodb:DeleteItem",
      "dynamodb:UpdateItem"
    ]
    resources = [
      aws_dynamodb_table.leases.arn
    ]
  }
}

resource "aws_iam_policy" "lambda_cleanup_ddb" {
  name   = "lambda_cleanup_ddb_access"
  policy = data.aws_iam_policy_document.lambda_cleanup_ddb_doc.json
}

resource "aws_iam_role_policy_attachment" "lambda_cleanup_ddb_attach" {
  role       = aws_iam_role.lambda_cleanup.name
  policy_arn = aws_iam_policy.lambda_cleanup_ddb.arn
}

############################
# CloudWatch Log Groups (managed in TF)
############################
resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/lambda_tts"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "cleanup" {
  name              = "/aws/lambda/lambda_cleanup"
  retention_in_days = 14
}


############################
# Lambdas (images + digests)
############################
resource "aws_lambda_function" "api" {
  function_name    = "lambda_tts"
  role             = aws_iam_role.lambda_api.arn
  package_type     = "Image"
  image_uri        = "${aws_ecr_repository.api.repository_url}:latest"
  source_code_hash = trimprefix(data.aws_ecr_image.api_latest.id, "sha256:")
  architectures    = ["x86_64"] # matches linux/amd64 build
  timeout          = 240
  memory_size      = 1024

  environment { variables = {} }

  depends_on = [
    null_resource.image_api,
    aws_iam_role_policy_attachment.lambda_api_logs,
    aws_cloudwatch_log_group.api
  ]
}

resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = true
    allow_origins     = ["*"]
    allow_methods     = ["*"]
    allow_headers     = ["data", "keep-alive"]
    expose_headers    = ["keep-alive", "date"]
    max_age           = 86400
  }
}

resource "aws_lambda_function" "cleanup" {
  function_name    = "lambda_cleanup"
  role             = aws_iam_role.lambda_cleanup.arn
  package_type     = "Image"
  image_uri        = "${aws_ecr_repository.cleanup.repository_url}:latest"
  source_code_hash = trimprefix(data.aws_ecr_image.cleanup_latest.id, "sha256:")
  architectures    = ["x86_64"]
  timeout          = 120
  memory_size      = 512

  depends_on = [
    null_resource.image_cleanup,
    aws_iam_role_policy_attachment.lambda_cleanup_logs,
    aws_cloudwatch_log_group.cleanup
  ]
}
