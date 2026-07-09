# Frontend React/Vite

SPA del proyecto Air Quality Alerts Bogotá.

## Funciones

- Dashboard GIS con Leaflet.
- Carga manual de archivos.
- Muestreo automático con opción de descargar todas las estaciones registradas.
- Barra de progreso alimentada desde `/api/jobs/{job_id}`.
- Panel separado de sesiones para revisar historial y cargar resultados anteriores en el mapa.
- Build estático listo para S3 + CloudFront.

## Desarrollo local

```bash
npm install
cp .env.example .env
npm run dev
```

`frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Producción CloudFront

No definas `VITE_API_BASE_URL` si usas la infraestructura Terraform de este repositorio. La app consumirá `/api/*` por el mismo dominio CloudFront y CloudFront lo reenviará al ALB del backend.

```bash
npm run build
```

El resultado queda en `dist/`.
