output "bucket_name" {
  description = "Private S3 bucket in eu-south-2."
  value       = aws_s3_bucket.lab.id
}

output "distribution_id" {
  value = aws_cloudfront_distribution.lab.id
}

output "distribution_domain_name" {
  value = aws_cloudfront_distribution.lab.domain_name
}

output "file_url" {
  description = "Public HTTPS URL of the uploaded example file through CloudFront."
  value       = "https://${aws_cloudfront_distribution.lab.domain_name}/${aws_s3_object.example.key}"
}

output "s3_file_url" {
  description = "Anonymous access to this direct S3 URL should return AccessDenied."
  value       = "https://${aws_s3_bucket.lab.bucket_regional_domain_name}/${aws_s3_object.example.key}"
}
