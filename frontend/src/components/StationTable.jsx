import { useMemo, useState } from 'react';
import Modal from './Modal.jsx';
import StatusBadge from './StatusBadge.jsx';

export default function StationTable({ rows = [] }) {
  const [query, setQuery] = useState('');
  const [tierFilter, setTierFilter] = useState('all');
  const [selectedRow, setSelectedRow] = useState(null);

  const filteredRows = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return rows.filter((row) => {
      const rowText = `${row.station_id || ''} ${row.station_name || ''} ${row.tier_actual || ''} ${row.station_current_status || ''}`.toLowerCase();
      const tier = String(row.tier_actual || 'sin dato').toLowerCase();
      const matchQuery = !normalizedQuery || rowText.includes(normalizedQuery);
      const matchTier = tierFilter === 'all' || tier.includes(tierFilter);
      return matchQuery && matchTier;
    });
  }, [query, rows, tierFilter]);

  const declaredAlerts = rows.filter((row) => String(row.tier_actual || '').toLowerCase().match(/prev|alerta|emerg/)).length;

  return (
    <section className="overflow-hidden rounded-[2rem] border border-white/10 bg-white/95 text-slate-900 shadow-soft">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-5 py-4">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-600">Resultados</p>
          <h2 className="text-xl font-black tracking-tight">Resumen por estación</h2>
          <p className="mt-1 text-sm text-slate-500">Filtra, revisa y abre el detalle operativo de cada estación.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Pill label={rows.length ? `${rows.length} estaciones` : 'Sin cálculo'} />
          <Pill label={`${declaredAlerts} con alerta`} tone={declaredAlerts ? 'danger' : 'ok'} />
        </div>
      </div>

      {rows.length ? (
        <>
          <div className="grid gap-3 border-b border-slate-200 bg-slate-50 px-5 py-4 md:grid-cols-[1fr_220px]">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Buscar por estación, ID o estado..."
            />
            <select value={tierFilter} onChange={(event) => setTierFilter(event.target.value)}>
              <option value="all">Todos los estados</option>
              <option value="normal">Normal</option>
              <option value="prev">Prevención</option>
              <option value="alerta">Alerta</option>
              <option value="emerg">Emergencia</option>
            </select>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-white text-xs uppercase tracking-[0.12em] text-slate-500">
                <tr>
                  <th className="px-5 py-3 text-left">Estación</th>
                  <th className="px-5 py-3 text-left">Fecha</th>
                  <th className="px-5 py-3 text-right">Medición</th>
                  <th className="px-5 py-3 text-right">Media 24h</th>
                  <th className="px-5 py-3 text-left">Tier</th>
                  <th className="px-5 py-3 text-left">Estado</th>
                  <th className="px-5 py-3 text-right">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredRows.map((row, index) => (
                  <tr key={`${row.station_id || row.station_name}-${index}`} className="transition hover:bg-blue-50/60">
                    <td className="px-5 py-4">
                      <p className="font-black text-slate-950">{row.station_name || 'Sin estación'}</p>
                      {row.station_id && <p className="mt-0.5 text-xs font-bold text-slate-400">ID {row.station_id}</p>}
                    </td>
                    <td className="px-5 py-4 text-slate-600">{row.timestamp || 'Sin dato'}</td>
                    <td className="px-5 py-4 text-right font-bold">{formatNumber(row.value)}</td>
                    <td className="px-5 py-4 text-right font-bold">{formatNumber(row.rolling_avg_24h)}</td>
                    <td className="px-5 py-4"><StatusBadge status={row.tier_actual} compact /></td>
                    <td className="px-5 py-4 text-slate-700">{row.station_current_status || 'Sin estado'}</td>
                    <td className="px-5 py-4 text-right">
                      <button
                        type="button"
                        onClick={() => setSelectedRow(row)}
                        className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-black text-slate-600 shadow-sm transition hover:border-blue-200 hover:bg-blue-50 hover:text-blue-700"
                      >
                        Detalle
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {!filteredRows.length && (
            <div className="px-5 py-8 text-sm font-semibold text-slate-500">
              No hay estaciones que coincidan con el filtro actual.
            </div>
          )}
        </>
      ) : (
        <EmptyState />
      )}

      <Modal
        open={Boolean(selectedRow)}
        onClose={() => setSelectedRow(null)}
        title={selectedRow?.station_name || 'Detalle de estación'}
        eyebrow="Análisis operativo"
        footer={
          <button type="button" onClick={() => setSelectedRow(null)} className="btn-primary max-w-xs">
            Cerrar detalle
          </button>
        }
      >
        {selectedRow && (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-slate-200 bg-slate-50 p-4">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">Estado calculado</p>
                <p className="mt-1 text-lg font-black text-slate-950">{selectedRow.station_current_status || 'Sin estado'}</p>
              </div>
              <StatusBadge status={selectedRow.tier_actual} />
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <DetailItem label="ID estación" value={selectedRow.station_id || 'Sin dato'} />
              <DetailItem label="Fecha/hora" value={selectedRow.timestamp || 'Sin dato'} />
              <DetailItem label="Medición" value={formatNumber(selectedRow.value)} />
              <DetailItem label="Media móvil 24h" value={formatNumber(selectedRow.rolling_avg_24h)} />
              <DetailItem label="Contaminante" value={selectedRow.pollutant || 'PM2.5'} />
              <DetailItem label="Tier" value={selectedRow.tier_actual || 'Sin dato'} />
            </div>
          </div>
        )}
      </Modal>
    </section>
  );
}

function EmptyState() {
  return (
    <div className="grid place-items-center px-5 py-12 text-center">
      <div className="max-w-md">
        <div className="mx-auto grid h-16 w-16 place-items-center rounded-3xl bg-blue-50 text-3xl text-blue-600 ring-1 ring-blue-100">⌁</div>
        <h3 className="mt-4 text-lg font-black text-slate-950">Todavía no hay resultados calculados</h3>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          Ejecuta una carga manual o un muestreo automático para visualizar aquí el último estado calculado por estación.
        </p>
      </div>
    </div>
  );
}

function Pill({ label, tone = 'default' }) {
  const className = tone === 'danger'
    ? 'bg-rose-50 text-rose-800 ring-rose-100'
    : tone === 'ok'
      ? 'bg-emerald-50 text-emerald-800 ring-emerald-100'
      : 'bg-slate-100 text-slate-600 ring-slate-200';
  return <span className={`rounded-full px-4 py-2 text-xs font-black ring-1 ${className}`}>{label}</span>;
}

function DetailItem({ label, value }) {
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-4">
      <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">{label}</p>
      <p className="mt-1 break-words font-black text-slate-950">{value}</p>
    </div>
  );
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return 'Sin dato';
  return Number(value).toLocaleString('es-CO', { maximumFractionDigits: 2 });
}
