resource "aws_s3_bucket" "lab" {
  # Terraform appends a unique suffix to the prefix.
  bucket_prefix = "dz7-private-"

  # Disposable homework bucket: destroy also removes any extra uploaded objects.
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "lab" {
  bucket = aws_s3_bucket.lab.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "lab" {
  bucket = aws_s3_bucket.lab.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_object" "example" {
  bucket       = aws_s3_bucket.lab.id
  key          = "example.txt"
  source       = "${path.module}/files/example.txt"
  source_hash  = filemd5("${path.module}/files/example.txt")
  content_type = "text/plain; charset=utf-8"

  depends_on = [
    aws_s3_bucket_public_access_block.lab,
    aws_s3_bucket_ownership_controls.lab,
  ]
}

resource "aws_cloudfront_origin_access_control" "lab" {
  name                              = aws_s3_bucket.lab.id
  description                       = "OAC for the private DZ7 S3 bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

resource "aws_cloudfront_distribution" "lab" {
  enabled             = true
  comment             = "DZ7 private S3 with OAC"
  wait_for_deployment = true
  retain_on_delete    = false

  origin {
    domain_name              = aws_s3_bucket.lab.bucket_regional_domain_name
    origin_id                = "dz7-s3"
    origin_access_control_id = aws_cloudfront_origin_access_control.lab.id
  }

  default_cache_behavior {
    target_origin_id       = "dz7-s3"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.optimized.id
    compress               = true
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  # No WAF association or flat-rate subscription: standard pay-as-you-go distribution.
  tags = {
    Name = "dz7-s3-cloudfront"
  }
}

data "aws_iam_policy_document" "cloudfront_read" {
  statement {
    sid       = "AllowCloudFrontReadOnly"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.lab.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.lab.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "lab" {
  bucket = aws_s3_bucket.lab.id
  policy = data.aws_iam_policy_document.cloudfront_read.json

  depends_on = [aws_s3_bucket_public_access_block.lab]
}
