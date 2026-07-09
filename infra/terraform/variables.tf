variable "aws_region" {
  description = "Región AWS donde se desplegará la solución."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Nombre base para recursos AWS."
  type        = string
  default     = "air-quality-alerts"
}

variable "environment" {
  description = "Ambiente del despliegue."
  type        = string
  default     = "prod"
}

variable "backend_image_uri" {
  description = "URI completa de la imagen Docker del backend en ECR. Ej: 123456789.dkr.ecr.us-east-1.amazonaws.com/repo:tag"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR principal de la VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "desired_count" {
  description = "Cantidad de tareas Fargate del backend."
  type        = number
  default     = 1
}

variable "backend_cpu" {
  description = "CPU Fargate para el backend."
  type        = number
  default     = 1024
}

variable "backend_memory" {
  description = "Memoria Fargate para el backend."
  type        = number
  default     = 2048
}

variable "allowed_origins" {
  description = "Orígenes CORS permitidos. Déjalo vacío para usar same-origin vía CloudFront y * durante pruebas."
  type        = string
  default     = "*"
}

variable "jsf_target_url" {
  description = "URL del portal JSF/SISAIRE que usa Playwright para descarga automática."
  type        = string
  default     = "https://sisaire.ideam.gov.co/ideam-sisaire-web/consultas.xhtml"
  sensitive   = true
}

variable "create_rds" {
  description = "Crea una instancia PostgreSQL RDS para persistir sesiones/jobs. Si es false, el backend usa SQLite sobre EFS."
  type        = bool
  default     = true
}

variable "db_name" {
  description = "Nombre de base de datos PostgreSQL."
  type        = string
  default     = "airquality"
}

variable "db_username" {
  description = "Usuario administrador de PostgreSQL."
  type        = string
  default     = "airquality"
}

variable "db_instance_class" {
  description = "Clase de instancia RDS para el proyecto de portafolio."
  type        = string
  default     = "db.t4g.micro"
}

variable "db_allocated_storage" {
  description = "Almacenamiento inicial RDS en GB."
  type        = number
  default     = 20
}

variable "force_delete_ecr" {
  description = "Permite borrar el repo ECR aunque tenga imágenes. Útil en labs; usar con cuidado en producción."
  type        = bool
  default     = false
}
