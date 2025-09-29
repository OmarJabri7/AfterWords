############################
# EventBridge Scheduler for session cleanups
############################

# 1) One schedule group to keep things organized
resource "aws_scheduler_schedule_group" "sessions" {
  name = "membox-session-schedules"
}

# 2) Role that *EventBridge Scheduler* assumes to invoke your cleanup lambda
data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "scheduler_invoke_cleanup" {
  name               = "membox-scheduler-invoke-cleanup"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

data "aws_iam_policy_document" "scheduler_invoke_cleanup_doc" {
  statement {
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.cleanup.arn]
  }
}

resource "aws_iam_policy" "scheduler_invoke_cleanup_pol" {
  name   = "membox-scheduler-invoke-cleanup-pol"
  policy = data.aws_iam_policy_document.scheduler_invoke_cleanup_doc.json
}

resource "aws_iam_role_policy_attachment" "scheduler_invoke_cleanup_attach" {
  role       = aws_iam_role.scheduler_invoke_cleanup.name
  policy_arn = aws_iam_policy.scheduler_invoke_cleanup_pol.arn
}

# 3) Let Scheduler actually call your cleanup function
resource "aws_lambda_permission" "allow_scheduler_cleanup" {
  statement_id  = "AllowSchedulerInvokeCleanup"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.cleanup.function_name
  principal     = "scheduler.amazonaws.com"
}

# (Optional but recommended) Output handy values for your Streamlit app
output "scheduler_group_name" {
  value = aws_scheduler_schedule_group.sessions.name
}

output "scheduler_role_arn" {
  value = aws_iam_role.scheduler_invoke_cleanup.arn
}

output "cleanup_lambda_arn" {
  value = aws_lambda_function.cleanup.arn
}
