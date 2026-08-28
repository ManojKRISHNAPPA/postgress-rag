terraform {
  backend "s3" {
    bucket         = "quantam-vector-infra-statefile-backup-2"
    key            = "quantam-vector/1-network/terraform.tfstate"
    region         = "ap-northeast-1"
    dynamodb_table = "quantam-vector-terraform-locks"
    encrypt        = true
  }
}