import { useEffect, useMemo, useState } from 'react';
import ProcessPanel from './components/ProcessPanel.jsx';
import BogotaMap from './components/BogotaMap.jsx';
import StationTable from './components/StationTable.jsx';
import Modal from './components/Modal.jsx';
import { fetchDemoGeojson } from './services/api.js';

const EMPTY_RESULT = {
  station_summary: [],
  stations_geojson: null,
};

export default function App() {
  const [result, setResult] = useState(EMPTY_RESULT);
  const [demoGeojson, setDemoGeojson] = useState(null);
  const [activeProcess, setActiveProcess] = useState('manual');
  const [showAbout, setShowAbout] = useState(false);

  useEffect(() => {
    fetchDemoGeojson().then(setDemoGeojson).catch(() => setDemoGeojson(null));
  }, []);

  const geojson = useMemo(
    () => result?.stations_geojson || demoGeojson,
    [result?.stations_geojson, demoGeojson],
  );

  const totalAlerts = Number(result?.declared_alerts || 0);
  const totalStations = Number(result?.stations || geojson?.features?.length || 0);
  const totalRows = Number(result?.rows || 0);
  const hasCalculatedResult = Boolean(result?.result_id);

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.38),_transparent_34%),radial-gradient(circle_at_80%_0%,_rgba(14,165,233,0.20),_transparent_30%),linear-gradient(135deg,_#020617_0%,_#0f172a_45%,_#172554_100%)] text-slate-100">
      <section className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-5 px-4 py-5 md:px-6 lg:px-8">
        <header className="overflow-hidden rounded-[2.25rem] border border-white/10 bg-white/10 shadow-soft backdrop-blur">
          <div className="grid gap-5 p-5 md:grid-cols-[1fr_auto] md:items-start md:p-7">
            <div>
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-sky-300/20 bg-sky-300/10 px-3 py-1.5 text-[11px] font-black uppercase tracking-[0.18em] text-sky-100">
                <span className="h-2 w-2 rounded-full bg-emerald-300 shadow-[0_0_20px_rgba(110,231,183,0.9)]" />
                Bogotá · PM2.5 · GIS
              </div>
              <h1 className="max-w-4xl text-3xl font-black leading-none tracking-[-0.045em] text-white md:text-5xl lg:text-6xl">
                Centro de monitoreo de alertas de calidad del aire
              </h1>
              <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-300 md:text-base">
                Carga archivos CSV/Excel, calcula medias móviles de 24 horas, valida persistencia en 48 lecturas y visualiza el estado de las estaciones sobre un mapa tipo GIS de Bogotá.
              </p>

              <div className="mt-5 flex flex-wrap gap-3">
                <a href="#workflow" className="btn-hero-primary">Iniciar cálculo</a>
                <button type="button" onClick={() => setShowAbout(true)} className="btn-hero-secondary">
                  Ver reglas del modelo
                </button>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-3 md:min-w-[420px] md:grid-cols-1 lg:grid-cols-3">
              <Metric label="Registros" value={totalRows || 'Demo'} description="Procesados" />
              <Metric label="Estaciones" value={totalStations} description="En mapa" />
              <Metric label="Alertas" value={totalAlerts} description="Declaradas" tone={totalAlerts > 0 ? 'danger' : 'ok'} />
            </div>
          </div>

          <div className="grid gap-px border-t border-white/10 bg-white/10 md:grid-cols-3">
            <HeroStep number="01" title="Entrada flexible" text="Archivo manual o descarga automática desde portal con Playwright." />
            <HeroStep number="02" title="Motor trazable" text="Media móvil 24h, monitoreo de 48 lecturas y regla del 75%." />
            <HeroStep number="03" title="Salida ejecutiva" text="Memorias CSV/Excel, resumen por estación y GeoJSON para mapa." />
          </div>
        </header>

        <section id="workflow" className="grid gap-5 lg:grid-cols-[440px_1fr] lg:items-start">
          <ProcessPanel
            result={result}
            setResult={setResult}
            activeProcess={activeProcess}
            setActiveProcess={setActiveProcess}
          />

          <section className="overflow-hidden rounded-[2rem] border border-white/10 bg-white/95 text-slate-900 shadow-soft">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-600">Vista GIS</p>
                <h2 className="text-xl font-black tracking-tight">Mapa de estaciones en Bogotá</h2>
                <p className="mt-1 text-sm text-slate-500">
                  {hasCalculatedResult ? 'Datos calculados desde el último proceso ejecutado.' : 'Catálogo CAR/SISAIRE cargado desde GeoJSON local.'}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <MapPill label="Normal" dot="bg-emerald-500" />
                <MapPill label="Prevención" dot="bg-amber-500" />
                <MapPill label="Alerta" dot="bg-rose-600" />
                <MapPill label="Emergencia" dot="bg-red-950" />
              </div>
            </div>
            <BogotaMap geojson={geojson} />
          </section>
        </section>

        <StationTable rows={result?.station_summary || []} />
      </section>

      <Modal
        open={showAbout}
        onClose={() => setShowAbout(false)}
        title="Reglas de cálculo del motor PM2.5"
        eyebrow="Criterios operativos"
        size="lg"
        footer={
          <button type="button" onClick={() => setShowAbout(false)} className="btn-primary max-w-xs">
            Entendido
          </button>
        }
      >
        <div className="grid gap-4 text-sm leading-6 text-slate-600 md:grid-cols-2">
          <InfoCard title="Media móvil" text="Por cada estación se calcula una media móvil de 24 horas con lecturas válidas suficientes para evitar decisiones con datos incompletos." />
          <InfoCard title="Monitoreo" text="Cuando se supera un umbral, inicia una ventana de seguimiento posterior de 48 lecturas para validar si el evento persiste." />
          <InfoCard title="Persistencia" text="La alerta se declara si el contaminante supera el umbral durante más del 75% del periodo de monitoreo." />
          <InfoCard title="Salida" text="El motor devuelve memorias de cálculo en CSV, resumen por estación y GeoJSON listo para visualización GIS." />
        </div>

        <div className="mt-5 overflow-hidden rounded-3xl border border-slate-200">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase tracking-[0.14em] text-slate-500">
              <tr>
                <th className="px-4 py-3 text-left">Tier</th>
                <th className="px-4 py-3 text-left">Rango PM2.5</th>
                <th className="px-4 py-3 text-left">Interpretación</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              <ThresholdRow tier="Prevención" range="38 - 55" text="Evento inicial que requiere seguimiento." />
              <ThresholdRow tier="Alerta" range="56 - 150" text="Condición crítica que debe escalarse." />
              <ThresholdRow tier="Emergencia" range=">= 151" text="Escenario severo para atención prioritaria." />
            </tbody>
          </table>
        </div>
      </Modal>
    </main>
  );
}

function Metric({ label, value, description, tone = 'default' }) {
  const toneClass = tone === 'danger' ? 'text-rose-200' : tone === 'ok' ? 'text-emerald-200' : 'text-white';
  return (
    <div className="rounded-3xl border border-white/10 bg-white/10 p-4 backdrop-blur transition hover:bg-white/[0.14]">
      <span className="block text-[10px] font-black uppercase tracking-[0.14em] text-slate-300">{label}</span>
      <strong className={`mt-1 block text-3xl font-black tracking-tight ${toneClass}`}>{value}</strong>
      <span className="mt-1 block text-xs font-bold text-slate-300">{description}</span>
    </div>
  );
}

function HeroStep({ number, title, text }) {
  return (
    <article className="bg-white/[0.06] p-5 backdrop-blur">
      <p className="text-xs font-black text-sky-200">{number}</p>
      <h3 className="mt-2 text-sm font-black text-white">{title}</h3>
      <p className="mt-1 text-sm leading-6 text-slate-300">{text}</p>
    </article>
  );
}

function MapPill({ label, dot }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-black text-slate-600">
      <span className={`h-2.5 w-2.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}

function InfoCard({ title, text }) {
  return (
    <article className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
      <h3 className="font-black text-slate-950">{title}</h3>
      <p className="mt-2">{text}</p>
    </article>
  );
}

function ThresholdRow({ tier, range, text }) {
  return (
    <tr>
      <td className="px-4 py-3 font-black text-slate-950">{tier}</td>
      <td className="px-4 py-3 font-bold text-slate-700">{range}</td>
      <td className="px-4 py-3 text-slate-600">{text}</td>
    </tr>
  );
}
