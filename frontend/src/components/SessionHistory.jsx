import { useEffect, useState } from 'react';
import { fetchJobs, resultUrl } from '../services/api.js';

export default function SessionHistory({ onLoadResult }) {
  const [jobs, setJobs] = useState([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let mounted = true;
    let intervalId;

    async function load() {
      setLoading(true);
      setError('');
      try {
        const payload = await fetchJobs(30);
        if (mounted) setJobs(payload.jobs || []);
      } catch (err) {
        if (mounted) setError(err.message || 'No fue posible consultar las sesiones.');
      } finally {
        if (mounted) setLoading(false);
      }
    }

    load();
    intervalId = window.setInterval(load, 5000);
    return () => {
      mounted = false;
      window.clearInterval(intervalId);
    };
  }, []);

  return (
    <section className="overflow-hidden rounded-[2rem] border border-white/10 bg-white/95 text-slate-900 shadow-soft">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-600">Sesiones</p>
          <h2 className="text-xl font-black tracking-tight">Historial de ejecuciones</h2>
          <p className="mt-1 text-sm text-slate-500">Revisa progreso, errores y resultados sin mezclarlo con la tabla de estaciones.</p>
        </div>
        <span className="rounded-full bg-slate-100 px-4 py-2 text-xs font-black text-slate-600 ring-1 ring-slate-200">
          {loading ? 'Actualizando...' : `${jobs.length} sesiones`}
        </span>
      </div>

      {error && <div className="m-5 rounded-2xl bg-rose-50 p-4 text-sm font-bold text-rose-700 ring-1 ring-rose-100">{error}</div>}

      {jobs.length ? (
        <div className="divide-y divide-slate-100">
          {jobs.map((job) => (
            <SessionRow key={job.id} job={job} onLoadResult={onLoadResult} />
          ))}
        </div>
      ) : (
        <div className="grid place-items-center px-5 py-12 text-center">
          <div className="max-w-md">
            <div className="mx-auto grid h-16 w-16 place-items-center rounded-3xl bg-blue-50 text-3xl text-blue-600 ring-1 ring-blue-100">↻</div>
            <h3 className="mt-4 text-lg font-black text-slate-950">Sin sesiones registradas</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600">Ejecuta una carga manual o un muestreo automático para ver aquí el seguimiento separado.</p>
          </div>
        </div>
      )}
    </section>
  );
}

function SessionRow({ job, onLoadResult }) {
  const result = job.result_payload;
  const events = (job.events || []).slice(-3).reverse();
  const statusLabel = {
    queued: 'En cola',
    running: 'En proceso',
    completed: 'Completado',
    failed: 'Error',
  }[job.status] || job.status;

  return (
    <article className="px-5 py-4 transition hover:bg-blue-50/50">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] font-black uppercase tracking-[0.12em] text-slate-500">
              {job.kind === 'auto_sampling' ? 'Muestreo auto' : 'Carga manual'}
            </span>
            <span className={jobStatusClass(job.status)}>{statusLabel}</span>
          </div>
          <p className="mt-2 break-all text-xs font-bold text-slate-400">{job.id}</p>
          <p className="mt-2 text-sm font-black text-slate-800">{job.current_step || 'Proceso'}</p>
          <p className="mt-1 text-sm font-semibold text-slate-500">{job.message || job.error || 'Sin mensaje disponible.'}</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-black text-slate-950">{Math.round(Number(job.progress || 0))}%</p>
          <p className="text-[11px] font-bold text-slate-400">{formatDate(job.created_at)}</p>
        </div>
      </div>

      <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-blue-600 transition-all" style={{ width: `${Math.round(Number(job.progress || 0))}%` }} />
      </div>

      {result && (
        <div className="mt-4 grid gap-3 rounded-3xl bg-white p-4 ring-1 ring-slate-200 sm:grid-cols-4">
          <Metric label="Registros" value={result.rows || 0} />
          <Metric label="Estaciones" value={result.stations || 0} />
          <Metric label="Alertas" value={result.declared_alerts || 0} />
          <div className="flex flex-col gap-2">
            <button type="button" onClick={() => onLoadResult(result)} className="rounded-xl bg-blue-600 px-3 py-2 text-xs font-black text-white transition hover:bg-blue-700">
              Ver en mapa
            </button>
            {result.download_excel_url && (
              <a href={resultUrl(result.download_excel_url)} className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-center text-xs font-black text-slate-600 transition hover:bg-slate-50">
                Excel
              </a>
            )}
          </div>
        </div>
      )}

      {events.length > 0 && (
        <div className="mt-3 space-y-1">
          {events.map((event) => (
            <p key={`${job.id}-${event.timestamp}-${event.progress}`} className="text-xs font-semibold text-slate-500">
              <span className="font-black text-slate-800">{event.progress}%</span> · {event.step} · {event.message}
            </p>
          ))}
        </div>
      )}
    </article>
  );
}

function Metric({ label, value }) {
  return (
    <div>
      <p className="text-[11px] font-black uppercase tracking-[0.12em] text-slate-400">{label}</p>
      <p className="mt-1 text-lg font-black text-slate-950">{value}</p>
    </div>
  );
}

function jobStatusClass(status) {
  const base = 'rounded-full px-3 py-1 text-[11px] font-black uppercase tracking-[0.12em]';
  if (status === 'completed') return `${base} bg-emerald-50 text-emerald-700`;
  if (status === 'failed') return `${base} bg-rose-50 text-rose-700`;
  if (status === 'running') return `${base} bg-amber-50 text-amber-700`;
  return `${base} bg-blue-50 text-blue-700`;
}

function formatDate(value) {
  if (!value) return 'Sin fecha';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('es-CO', { dateStyle: 'short', timeStyle: 'short' });
}
