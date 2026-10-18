output "db_identifier" {
  value = aws_db_instance.postgres.identifier
}

output "db_endpoint" {
  description = "RDS endpoint including port."
  value       = aws_db_instance.postgres.endpoint
}

output "db_host" {
  description = "Hostname for psql -h (without port)."
  value       = aws_db_instance.postgres.address
}

output "master_secret_arn" {
  description = "Secret identifier, not the password. Retrieve the password privately in AWS Console."
  value       = aws_db_instance.postgres.master_user_secret[0].secret_arn
}

output "psql_command" {
  value = "psql \"host=${aws_db_instance.postgres.address} port=5432 user=postgres dbname=postgres sslmode=require\" -W"
}
