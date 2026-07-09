# Infraestructura AWS: Fargate + RDS PostgreSQL + S3/CloudFront

Este módulo deja el proyecto listo para desplegar como portafolio cloud:

- Backend FastAPI en ECS Fargate detrás de Application Load Balancer.
- PostgreSQL en RDS para persistir sesiones/jobs y progreso.
- EFS cifrado para conservar archivos generados por el backend (`outputs`).
- Frontend React publicado en S3 privado con CloudFront.
- CloudFront enruta `/api/*` hacia el ALB para evitar problemas de mixed content desde HTTPS.
- Outputs con URLs para pruebas.

## Flujo recomendado

1. Crear la infraestructura inicial para obtener el repositorio ECR:

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edita backend_image_uri con un valor temporal válido o crea primero el repo ECR por consola si prefieres.
terraform init
terraform plan
terraform apply
```

2. Construir y subir la imagen del backend:

```bash
../../scripts/push_backend_ecr.sh us-east-1 <account-id> air-quality-alerts-prod-backend latest
```

3. Actualizar `backend_image_uri` en `terraform.tfvars` con la imagen real y aplicar:

```bash
terraform apply
```

4. Publicar el frontend en S3 y limpiar caché CloudFront:

```bash
../../scripts/deploy_frontend_s3.sh <frontend_bucket_name> <cloudfront_distribution_id>
```

## Outputs útiles

```bash
terraform output frontend_cloudfront_url
terraform output api_health_url
terraform output backend_alb_url
terraform output ecr_repository_url
```

Para pruebas funcionales usa primero:

```bash
curl $(terraform output -raw api_health_url)
```
