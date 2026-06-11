# Frontend - Air Quality Alerts Bogotá

SPA construida con React, Vite, Tailwind CSS y Leaflet. La interfaz está diseñada como un dashboard de portafolio con carga drag-and-drop, modales de ayuda, confirmación de muestreo automático, resultados descargables y detalle operativo por estación.

## Scripts

```bash
npm install
npm run dev
npm run build
npm run preview
```

## Variables

Crea `frontend/.env` desde `.env.example`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Flujo de la vista

La aplicación tiene una única vista principal:

1. Hero tipo dashboard con métricas ejecutivas.
2. Panel de carga manual con drag-and-drop para CSV/Excel.
3. Modal de ayuda para formato esperado de datos.
4. Modal de confirmación antes de ejecutar muestreo automático con Playwright.
5. Indicador visual de progreso del cálculo.
6. Modal de resultados con descargas de memoria CSV, resumen y GeoJSON.
7. Mapa GIS de Bogotá con leyenda, tooltip y detalle lateral de estación.
8. Tabla resumen con búsqueda, filtro por tier y modal de detalle.

## Build estático

La carpeta `dist/` ya queda generada para despliegue estático.

```bash
npm run build
```
