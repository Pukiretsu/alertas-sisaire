output "frontend_cloudfront_url" {
  description = "URL pública HTTPS del frontend. También enruta /api/* al backend."
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}

output "api_health_url" {
  description = "URL HTTPS para probar healthcheck por CloudFront."
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}/api/health"
}

output "backend_alb_url" {
  description = "URL directa del ALB del backend. Útil para pruebas técnicas."
  value       = "http://${aws_lb.app.dns_name}"
}

output "backend_alb_health_url" {
  description = "Healthcheck directo contra el ALB."
  value       = "http://${aws_lb.app.dns_name}/api/health"
}

output "frontend_bucket_name" {
  description = "Bucket S3 privado donde se publica frontend/dist."
  value       = aws_s3_bucket.frontend.bucket
}

output "cloudfront_distribution_id" {
  description = "ID de distribución CloudFront para invalidaciones."
  value       = aws_cloudfront_distribution.frontend.id
}

output "ecr_repository_url" {
  description = "Repositorio ECR sugerido para subir la imagen del backend."
  value       = aws_ecr_repository.backend.repository_url
}

output "ecs_cluster_name" {
  description = "Cluster ECS Fargate."
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "Servicio ECS del backend."
  value       = aws_ecs_service.api.name
}

output "postgres_endpoint" {
  description = "Endpoint de RDS PostgreSQL si create_rds=true."
  value       = var.create_rds ? aws_db_instance.postgres[0].address : null
}
