import { useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import StatusBadge from './StatusBadge.jsx';

export default function BogotaMap({ geojson }) {
  const containerId = useRef(`map-${Math.random().toString(36).slice(2)}`);
  const mapRef = useRef(null);
  const layerRef = useRef(null);
  const [selectedStation, setSelectedStation] = useState(null);

  const features = geojson?.features || [];
  const mapSummary = useMemo(() => summarizeFeatures(features), [features]);

  // 1. Inicialización y Limpieza del Mapa
  useEffect(() => {
    if (!mapRef.current) {
      mapRef.current = L.map(containerId.current, {
        center: [4.711, -74.0721],
        zoom: 11,
        scrollWheelZoom: true,
        zoomControl: false, // Ocultamos el control nativo para un look más limpio
      });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors',
      }).addTo(mapRef.current);
    }

    // Cleanup fundamental para React 18
    return () => {
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
    };
  }, []);

  // 2. Renderizado de Capas (Features GeoJSON)
  useEffect(() => {
    if (!mapRef.current) return;

    if (layerRef.current) {
      layerRef.current.remove();
      layerRef.current = null;
    }

    if (!features.length) return;

    layerRef.current = L.geoJSON(geojson, {
      pointToLayer: (feature, latlng) => L.circleMarker(latlng, {
        radius: markerRadius(feature.properties?.tier_actual),
        fillOpacity: 0.92,
        weight: 3,
        color: '#ffffff',
        fillColor: statusColor(feature.properties?.tier_actual),
      }),
      onEachFeature: (feature, layer) => {
        const properties = feature.properties || {};
        layer.bindTooltip(properties.station_name || 'Estación', {
          direction: 'top',
          offset: [0, -12],
          opacity: 0.9,
        });
        layer.bindPopup(buildPopup(properties));
        layer.on('click', () => setSelectedStation(properties));
      },
    }).addTo(mapRef.current);

    const bounds = layerRef.current.getBounds();
    if (bounds.isValid()) {
      mapRef.current.fitBounds(bounds, { padding: [34, 34], maxZoom: 13 });
    }
  }, [features.length, geojson]);

  return (
    <div className="relative h-full w-full">
      {/* Panel Superior Izquierdo (Resumen Visual) */}
      <div className="absolute left-4 bottom-5 z-[400] hidden max-w-xs rounded-3xl border border-white/10 bg-slate-900/80 p-4 text-slate-100 shadow-2xl backdrop-blur-md md:block">
        <p className="text-xs font-black uppercase tracking-[0.16em] text-sky-400">Resumen visual</p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <MiniStat label="Estaciones" value={features.length} />
          <MiniStat label="Con alerta" value={mapSummary.withAlert} />
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-400">
          Haz clic sobre una estación para revisar medición, media móvil y estado actual.
        </p>
      </div>

      {/* Contenedor del Mapa (Full Screen) */}
      <div id={containerId.current} className="h-full w-full z-0 bg-[#0f172a] outline-none" />

      {/* Detalle de Estación Seleccionada */}
      {selectedStation && (
        <aside className="absolute bottom-6 left-4 right-4 z-[400] rounded-3xl border border-white/10 bg-slate-900/90 p-5 text-slate-100 shadow-2xl backdrop-blur-xl md:left-auto md:w-[360px] md:bottom-8 md:right-8">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.16em] text-sky-400">Estación seleccionada</p>
              <h3 className="mt-1 text-lg font-black leading-tight text-white">{selectedStation.station_name || 'Estación'}</h3>
            </div>
            <button
              type="button"
              onClick={() => setSelectedStation(null)}
              className="grid h-8 w-8 place-items-center rounded-full bg-white/10 text-lg font-black text-slate-300 transition hover:bg-rose-500 hover:text-white"
              aria-label="Cerrar detalle de estación"
            >
              ×
            </button>
          </div>

          <div className="mt-4">
            <StatusBadge status={selectedStation.tier_actual || selectedStation.estado_actual} />
          </div>

          <dl className="mt-5 grid grid-cols-2 gap-3 text-sm">
            <StationData label="Medición" value={formatNumber(selectedStation.value)} />
            <StationData label="Media 24h" value={formatNumber(selectedStation.rolling_avg_24h)} />
            <StationData label="Estado" value={selectedStation.estado_actual || selectedStation.station_current_status || 'Sin dato'} />
            <StationData label="Fecha" value={selectedStation.timestamp || 'Sin dato'} />
          </dl>
        </aside>
      )}
    </div>
  );
}

// === FUNCIONES DE APOYO Y UTILIDADES ===

function buildPopup(properties) {
  // Ajustado con colores más oscuros para combinar con el nuevo tema
  return `
    <div style="padding:14px; min-width:220px; font-family:Inter,system-ui,sans-serif;">
      <p style="margin:0 0 6px; font-size:11px; text-transform:uppercase; letter-spacing:.12em; font-weight:900; color:#0ea5e9;">Detalle de estación</p>
      <strong style="display:block; font-size:16px; color:#0f172a; line-height:1.2;">${properties.station_name || 'Estación'}</strong>
      <div style="margin-top:10px; display:grid; gap:6px; font-size:13px; color:#475569;">
        <span><b>Tier:</b> ${properties.tier_actual || 'Sin dato'}</span>
        <span><b>Medición:</b> ${formatNumber(properties.value)}</span>
        <span><b>Media 24h:</b> ${formatNumber(properties.rolling_avg_24h)}</span>
        <span><b>Fecha:</b> ${properties.timestamp || 'Sin dato'}</span>
      </div>
    </div>
  `;
}

function MiniStat({ label, value }) {
  return (
    <div className="rounded-2xl bg-white/5 p-3 text-center ring-1 ring-white/10">
      <p className="text-[10px] font-black uppercase tracking-[0.12em] text-slate-400">{label}</p>
      <p className="mt-1 text-xl font-black text-white">{value}</p>
    </div>
  );
}

function StationData({ label, value }) {
  return (
    <div className="rounded-2xl bg-white/5 p-3 ring-1 ring-white/10">
      <dt className="text-[10px] font-black uppercase tracking-[0.12em] text-slate-400">{label}</dt>
      <dd className="mt-1 break-words font-black text-slate-200">{value}</dd>
    </div>
  );
}

function summarizeFeatures(features) {
  return features.reduce(
    (acc, feature) => {
      const tier = String(feature.properties?.tier_actual || '').toLowerCase();
      if (tier.includes('prev') || tier.includes('alerta') || tier.includes('emerg')) acc.withAlert += 1;
      return acc;
    },
    { withAlert: 0 },
  );
}

function statusColor(status = '') {
  const value = String(status).toLowerCase();
  if (value.includes('emergencia')) return '#7f1d1d';
  if (value.includes('alerta')) return '#dc2626';
  if (value.includes('prevención') || value.includes('prevencion')) return '#f59e0b';
  if (value.includes('normal')) return '#16a34a';
  return '#64748b';
}

function markerRadius(status = '') {
  const value = String(status).toLowerCase();
  if (value.includes('emergencia')) return 14;
  if (value.includes('alerta')) return 13;
  if (value.includes('prevención') || value.includes('prevencion')) return 12;
  return 10;
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'Sin dato';
  return Number(value).toLocaleString('es-CO', { maximumFractionDigits: 2 });
}
