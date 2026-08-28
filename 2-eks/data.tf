data "terraform_remote_state" "network" {
  backend = "s3"

  config = {
    bucket = "quantam-vector-infra-statefile-backup-2"
    key    = "quantam-vector/1-network/terraform.tfstate"
    region = "ap-northeast-1"
  }
}