resource "aws_dynamodb_table" "leases" {
  name             = "leases"
  hash_key         = "session_id"
  billing_mode     = "PAY_PER_REQUEST"
  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"
  attribute {
    name = "session_id"
    type = "S"
  }

  attribute {
    name = "el_voice_id"
    type = "S"
  }

  attribute {
    name = "started_at_epoch"
    type = "N"
  }

  attribute {
    name = "expires_at_epoch"
    type = "N"
  }

  attribute {
    name = "status"
    type = "S"
  }

  global_secondary_index {
    name            = "by_status"
    hash_key        = "status"
    range_key       = "expires_at_epoch"
    projection_type = "ALL"
  }
  global_secondary_index {
    name            = "by_voice"
    hash_key        = "el_voice_id"
    range_key       = "started_at_epoch"
    projection_type = "ALL"
  }
}
