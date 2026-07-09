import { useEffect, useMemo, useRef, useState } from 'react';
import Modal from './Modal.jsx';
import { createAutoSamplingJob, createCalculationJob, fetchJob, fetchStationsList, resultUrl } from '../services/api.js';

const DEFAULT_STATIONS = '29586,31877,8249,31862,8254,8243,31867,31866,31865,31860';

const baseSteps = [
  'Crear sesión',
  'Preparar entrada',
  'Normalizar datos',
  'Calcular alertas',
  'Publicar artefactos',
];

export default function ProcessPanel({ result, setResult, activeProcess, setActiveProcess }) {
  const [file, setFile] = useState(null);
  const [pollutant, setPollutant] = useState('PM2.5');
  const [minReadings, setMinReadings] = useState(18);
  const [stations, setStations] = useState(DEFAULT_STATIONS);
  const [downloadAllRegistered, setDownloadAllRegistered] = useState(true);
  const [registeredStationsCount, setRegisteredStationsCount] = useState(0);
  const [startDate, setStartDate] = useState('2026-01-01');
  const [endDate, setEndDate] = useState('2026-01-03');
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [dragActive, setDragActive] = useState(false);
  const [showAutoConfirm, setShowAutoConfirm] = useState(false);
  const [showResultModal, setShowResultModal] = useState(false);
  const [showFormatModal, setShowFormatModal] = useState(false);
  const [steps, setSteps] = useState(baseSteps.map((label) => ({ label, state: 'pending' })));
  const [activeJob, setActiveJob] = useState(null);
  const inputRef = useRef(null);
  const pollingRef = useRef(null);

  useEffect(() => {
    fetchStationsList()
      .then((payload) => setRegisteredStationsCount(Number(payload?.count || 0)))
      .catch(() => setRegisteredStationsCount(0));
  }, []);

  useEffect(() => () => clearPolling(), []);

  const hasResult = Boolean(result?.result_id);
  const stationList = useMemo(
    () => stations.split(',').map((item) => item.trim()).filter(Boolean),
    [stations],
  );

  const progress = status === 'idle'
    ? 0
    : Math.round(Number(activeJob?.progress ?? (status === 'done' ? 100 : 0)));

  const downloadLinks = useMemo(() => {
    if (!hasResult) return [];
    const links = [
      ['Memoria de cálculo CSV', result.download_csv_url, 'Archivo trazable con cálculo completo'],
      ['Memoria de cálculo Excel', result.download_excel_url, 'Libro con resumen, detalle, parámetros y diccionario'],
      ['Resumen estaciones CSV', result.download_summary_url, 'Último estado consolidado por estación'],
      ['GeoJSON estaciones', result.geojson_url, 'Capa GIS para visualización en mapa'],
    ];
    if (result.download_raw_url) links.push(['CSV consolidado descargado', result.download_raw_url, 'Datos crudos descargados por estación y unificados']);
    return links.filter(([, href]) => Boolean(href));
  }, [hasResult, result]);

  async function runManualUpload(event) {
    event.preventDefault();
    setError('');

    if (!file) {
      setError('Selecciona un archivo CSV, XLSX o XLS antes de iniciar.');
      return;
    }

    startUiProcess('Creando sesión para carga manual...');

    try {
      const job = await createCalculationJob({ file, pollutant, minReadings });
      applyJob(job);
      monitorJob(job.id);
    } catch (err) {
      failProcess(err.message);
    }
  }

  async function runAutomaticSampling() {
    setShowAutoConfirm(false);
    setError('');
    startUiProcess('Creando sesión para descarga automática...');

    try {
      const job = await createAutoSamplingJob({
        estaciones: stationList,
        contaminante: pollutant,
        fecha_inicio: startDate,
        fecha_fin: endDate,
        min_valid_readings_24h: Number(minReadings),
        download_all_registered: downloadAllRegistered,
        continue_on_error: true,
      });
      applyJob(job);
      monitorJob(job.id);
    } catch (err) {
      failProcess(err.message);
    }
  }

  function startUiProcess(message) {
    clearPolling();
    setStatus('running');
    setActiveJob({ progress: 3, message, current_step: 'Preparación', events: [] });
    setSteps(buildStepsFromProgress(3));
  }

  function clearPolling() {
    if (pollingRef.current) window.clearInterval(pollingRef.current);
    pollingRef.current = null;
  }

  async function monitorJob(jobId) {
    clearPolling();

    async function poll() {
      try {
        const job = await fetchJob(jobId);
        applyJob(job);
        if (['completed', 'failed', 'cancelled'].includes(job.status)) clearPolling();
      } catch (err) {
        clearPolling();
        failProcess(err.message);
      }
    }

    await poll();
    pollingRef.current = window.setInterval(poll, 1500);
  }

  function applyJob(job) {
    setActiveJob(job);
    setSteps(buildStepsFromProgress(Number(job?.progress || 0), job?.status));

    if (job.status === 'completed' && job.result_payload) {
      setResult(job.result_payload);
      setStatus('done');
      setShowResultModal(true);
      return;
    }

    if (job.status === 'failed') {
      setError(job.error || job.message || 'No fue posible completar el proceso.');
      setStatus('error');
      return;
    }

    setStatus(job.status === 'queued' ? 'running' : job.status || 'running');
  }

  function failProcess(message) {
    setSteps((current) => current.map((step) => (step.state === 'running' ? { ...step, state: 'error' } : step)));
    setError(message || 'No fue posible completar el proceso.');
    setStatus('error');
  }

  function handleFileSelection(selectedFile) {
    if (!selectedFile) return;
    setFile(selectedFile);
    setError('');
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragActive(false);
    handleFileSelection(event.dataTransfer.files?.[0]);
  }

  return (
    <aside className="rounded-[2rem] border border-white/10 bg-white/95 p-5 text-slate-900 shadow-soft">
      <div className="mb-5 flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-600">Proceso de cálculo</p>
          <h2 className="mt-1 text-2xl font-black tracking-tight">Entrada de datos</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Cada ejecución crea una sesión consultable. La barra de carga refleja el progreso persistido por el backend.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowFormatModal(true)}
          className="shrink-0 rounded-full border border-blue-100 bg-blue-50 px-3 py-2 text-xs font-black text-blue-700 transition hover:bg-blue-100"
        >
          Ayuda
        </button>
      </div>

      <div className="mb-5 grid grid-cols-2 rounded-2xl bg-slate-100 p-1 text-sm font-black">
        <button type="button" onClick={() => setActiveProcess('manual')} className={tabClass(activeProcess === 'manual')}>
          Carga manual
        </button>
        <button type="button" onClick={() => setActiveProcess('auto')} className={tabClass(activeProcess === 'auto')}>
          Muestreo auto
        </button>
      </div>

      <StatusBanner
        status={status}
        activeProcess={activeProcess}
        file={file}
        stationCount={downloadAllRegistered ? registeredStationsCount || stationList.length : stationList.length}
        activeJob={activeJob}
      />

      {activeProcess === 'manual' ? (
        <form onSubmit={runManualUpload} className="mt-4 space-y-4">
          <Field label="Archivo CSV o Excel" hint="Arrastra el archivo o selecciónalo desde tu equipo.">
            <div
              onDragOver={(event) => {
                event.preventDefault();
                setDragActive(true);
              }}
              onDragLeave={() => setDragActive(false)}
              onDrop={handleDrop}
              className={`group cursor-pointer rounded-3xl border-2 border-dashed p-5 text-center transition ${dragActive ? 'border-blue-500 bg-blue-50' : 'border-slate-200 bg-slate-50 hover:border-blue-300 hover:bg-blue-50/60'}`}
              onClick={() => inputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') inputRef.current?.click();
              }}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={(event) => handleFileSelection(event.target.files?.[0])}
                className="hidden"
              />
              <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-white text-2xl shadow-sm ring-1 ring-slate-200 transition group-hover:scale-105">
                ↑
              </div>
              <p className="mt-3 text-sm font-black text-slate-800">
                {file ? file.name : 'Sube archivo de mediciones'}
              </p>
              <p className="mt-1 text-xs font-semibold text-slate-500">
                CSV, XLSX o XLS · {file ? formatBytes(file.size) : 'compatible con memorias manuales'}
              </p>
            </div>
          </Field>

          <CommonControls pollutant={pollutant} setPollutant={setPollutant} minReadings={minReadings} setMinReadings={setMinReadings} />

          <button type="submit" disabled={['running', 'queued'].includes(status)} className="btn-primary">
            {status === 'running' ? 'Procesando sesión...' : 'Generar memoria de cálculo'}
          </button>
        </form>
      ) : (
        <div className="mt-4 space-y-4">
          <CommonControls pollutant={pollutant} setPollutant={setPollutant} minReadings={minReadings} setMinReadings={setMinReadings} />

          <div className="grid grid-cols-2 gap-3">
            <Field label="Fecha inicio">
              <input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
            </Field>
            <Field label="Fecha fin">
              <input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
            </Field>
          </div>

          <label className="flex items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm font-bold text-slate-700">
            <input
              type="checkbox"
              checked={downloadAllRegistered}
              onChange={(event) => setDownloadAllRegistered(event.target.checked)}
              className="mt-1 h-4 w-4 rounded border-slate-300"
            />
            <span>
              Descargar todas las estaciones registradas
              <span className="mt-1 block text-xs font-semibold text-slate-500">
                {registeredStationsCount ? `${registeredStationsCount} estaciones del catálogo local.` : 'Usa el catálogo local disponible en el backend.'}
              </span>
            </span>
          </label>

          <Field label="Estaciones" hint="IDs separados por coma. Se ignora si activas todas las registradas.">
            <textarea
              value={stations}
              onChange={(event) => setStations(event.target.value)}
              rows="3"
              placeholder="29586,31877,8249"
              disabled={downloadAllRegistered}
              className={downloadAllRegistered ? 'opacity-60' : ''}
            />
          </Field>

          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-black text-slate-800">Estaciones a consultar</p>
              <span className="rounded-full bg-white px-3 py-1 text-xs font-black text-slate-600 shadow-sm">
                {downloadAllRegistered ? registeredStationsCount || 'Catálogo' : stationList.length}
              </span>
            </div>
            {!downloadAllRegistered && (
              <div className="mt-3 flex flex-wrap gap-2">
                {stationList.slice(0, 8).map((station) => (
                  <span key={station} className="rounded-full bg-white px-3 py-1 text-xs font-bold text-slate-600 shadow-sm ring-1 ring-slate-200">
                    {station}
                  </span>
                ))}
                {stationList.length > 8 && <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-black text-blue-700">+{stationList.length - 8}</span>}
              </div>
            )}
          </div>

          <button type="button" onClick={() => setShowAutoConfirm(true)} disabled={['running', 'queued'].includes(status)} className="btn-primary">
            {status === 'running' ? 'Descargando y calculando...' : 'Activar muestreo automático'}
          </button>
        </div>
      )}

      <ProcessSteps steps={steps} progress={progress} activeJob={activeJob} />

      {error && (
        <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm font-bold text-rose-700">
          <div className="flex gap-3">
            <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-rose-600 text-white">!</span>
            <div>
              <p className="font-black">No se pudo completar el proceso</p>
              <p className="mt-1 font-semibold">{error}</p>
            </div>
          </div>
        </div>
      )}

      {hasResult && <ResultCard result={result} downloadLinks={downloadLinks} onOpenDetails={() => setShowResultModal(true)} activeJob={activeJob} />}

      <Modal
        open={showAutoConfirm}
        onClose={() => setShowAutoConfirm(false)}
        title="Confirmar muestreo automático"
        eyebrow="Playwright por estación"
        footer={
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <button type="button" onClick={() => setShowAutoConfirm(false)} className="btn-secondary sm:w-auto">
              Cancelar
            </button>
            <button type="button" onClick={runAutomaticSampling} className="btn-primary sm:w-auto">
              Crear sesión e iniciar
            </button>
          </div>
        }
      >
        <div className="space-y-4 text-sm leading-6 text-slate-600">
          <p>
            La API descargará el CSV estación por estación, consolidará los archivos descargados y luego ejecutará el motor de cálculo. El progreso quedará registrado en la sesión.
          </p>
          <div className="grid gap-3 rounded-3xl border border-slate-200 bg-slate-50 p-4 sm:grid-cols-2">
            <ConfirmItem label="Contaminante" value={pollutant} />
            <ConfirmItem label="Lecturas válidas" value={`${minReadings}/24`} />
            <ConfirmItem label="Rango" value={`${startDate} a ${endDate}`} />
            <ConfirmItem label="Estaciones" value={downloadAllRegistered ? `${registeredStationsCount || 'Todas'} registradas` : stationList.length} />
          </div>
          <p className="rounded-2xl bg-amber-50 p-4 font-bold text-amber-900 ring-1 ring-amber-200">
            Verifica que el backend tenga configurada la variable JSF_TARGET_URL antes de iniciar el muestreo automático.
          </p>
        </div>
      </Modal>

      <Modal
        open={showResultModal && hasResult}
        onClose={() => setShowResultModal(false)}
        title="Memorias generadas correctamente"
        eyebrow="Proceso finalizado"
        size="lg"
        footer={
          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <button type="button" onClick={() => setShowResultModal(false)} className="btn-secondary sm:w-auto">
              Cerrar
            </button>
            <a href="#workflow" onClick={() => setShowResultModal(false)} className="btn-primary text-center sm:w-auto">
              Ver mapa actualizado
            </a>
          </div>
        }
      >
        <div className="grid gap-4 md:grid-cols-3">
          <ResultMetric label="Registros" value={result?.rows || 0} />
          <ResultMetric label="Estaciones" value={result?.stations || 0} />
          <ResultMetric label="Alertas" value={result?.declared_alerts || 0} />
        </div>

        <div className="mt-5 grid gap-3">
          {downloadLinks.map(([label, href, description]) => (
            <a key={label} href={resultUrl(href)} className="group rounded-3xl border border-slate-200 bg-white p-4 transition hover:border-blue-200 hover:bg-blue-50">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-black text-slate-950">{label}</p>
                  <p className="mt-1 text-sm text-slate-500">{description}</p>
                </div>
                <span className="grid h-10 w-10 place-items-center rounded-full bg-slate-100 font-black text-slate-500 transition group-hover:bg-blue-600 group-hover:text-white">↓</span>
              </div>
            </a>
          ))}
        </div>
      </Modal>

      <Modal open={showFormatModal} onClose={() => setShowFormatModal(false)} title="Formato recomendado de entrada" eyebrow="Carga manual" footer={<button type="button" onClick={() => setShowFormatModal(false)} className="btn-primary max-w-xs">Entendido</button>}>
        <div className="space-y-4 text-sm leading-6 text-slate-600">
          <p>
            Para generar memorias confiables, el archivo debe incluir datos por estación, fecha/hora y concentración del contaminante. El motor acepta CSV, XLSX y XLS.
          </p>
          <div className="overflow-hidden rounded-3xl border border-slate-200">
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-[0.14em] text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left">Campo</th>
                  <th className="px-4 py-3 text-left">Ejemplo</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                <FormatRow field="station_id / station_name" example="8249 / Kennedy" />
                <FormatRow field="timestamp" example="2026-01-01 08:00:00" />
                <FormatRow field="pollutant" example="PM2.5" />
                <FormatRow field="value" example="42.7" />
                <FormatRow field="latitude / longitude" example="4.626 / -74.152" />
              </tbody>
            </table>
          </div>
        </div>
      </Modal>
    </aside>
  );
}

function StatusBanner({ status, activeProcess, file, stationCount, activeJob }) {
  const content = {
    idle: {
      title: activeProcess === 'manual' ? 'Listo para cargar archivo' : 'Listo para muestreo automático',
      text: activeProcess === 'manual' ? 'Selecciona un archivo para comenzar el cálculo.' : `${stationCount} estaciones configuradas para descarga.`,
      className: 'border-blue-100 bg-blue-50 text-blue-900',
    },
    running: {
      title: activeJob?.current_step || 'Proceso en ejecución',
      text: activeJob?.message || (activeProcess === 'manual' ? `Procesando ${file?.name || 'archivo seleccionado'}...` : 'Descargando datos y calculando alertas...'),
      className: 'border-amber-100 bg-amber-50 text-amber-900',
    },
    queued: {
      title: 'Sesión en cola',
      text: activeJob?.message || 'Esperando inicio del procesamiento.',
      className: 'border-amber-100 bg-amber-50 text-amber-900',
    },
    done: {
      title: 'Resultados disponibles',
      text: 'Ya puedes descargar memorias y revisar el mapa actualizado.',
      className: 'border-emerald-100 bg-emerald-50 text-emerald-900',
    },
    error: {
      title: 'Requiere revisión',
      text: 'Valida el archivo, la API o la configuración del portal.',
      className: 'border-rose-100 bg-rose-50 text-rose-900',
    },
  }[status] || {};

  return (
    <div className={`rounded-3xl border p-4 ${content.className}`}>
      <div className="flex items-center gap-3">
        <span className={`h-3 w-3 rounded-full ${status === 'running' || status === 'queued' ? 'animate-pulse bg-amber-500' : status === 'done' ? 'bg-emerald-500' : status === 'error' ? 'bg-rose-500' : 'bg-blue-500'}`} />
        <div>
          <p className="text-sm font-black">{content.title}</p>
          <p className="mt-0.5 text-xs font-semibold opacity-80">{content.text}</p>
        </div>
      </div>
      {activeJob?.id && <p className="mt-3 break-all text-[11px] font-bold opacity-70">Sesión: {activeJob.id}</p>}
    </div>
  );
}

function ResultCard({ result, downloadLinks, onOpenDetails, activeJob }) {
  return (
    <div className="mt-4 rounded-3xl border border-emerald-200 bg-emerald-50 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-black text-emerald-900">Proceso finalizado</p>
          <p className="mt-1 text-sm text-emerald-800">
            {result.rows} registros, {result.stations} estaciones y {result.declared_alerts} alertas declaradas.
          </p>
          {activeJob?.id && <p className="mt-1 break-all text-[11px] font-bold text-emerald-700">Sesión {activeJob.id}</p>}
        </div>
        <button type="button" onClick={onOpenDetails} className="rounded-full bg-white px-3 py-1.5 text-xs font-black text-emerald-800 shadow-sm transition hover:bg-emerald-100">
          Ver
        </button>
      </div>
      <div className="mt-3 grid gap-2">
        {downloadLinks.slice(0, 3).map(([label, href]) => (
          <a key={label} href={resultUrl(href)} className="download-link">
            Descargar {label}
          </a>
        ))}
      </div>
    </div>
  );
}

function CommonControls({ pollutant, setPollutant, minReadings, setMinReadings }) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <Field label="Contaminante">
        <select value={pollutant} onChange={(event) => setPollutant(event.target.value)}>
          <option value="PM2.5">PM2.5</option>
          <option value="PM10">PM10</option>
          <option value="O3">O3</option>
        </select>
      </Field>
      <Field label="Lecturas válidas 24h">
        <input type="number" min="1" max="24" value={minReadings} onChange={(event) => setMinReadings(Number(event.target.value))} />
      </Field>
    </div>
  );
}

function Field({ label, hint, children }) {
  return (
    <label className="block text-sm font-black text-slate-700">
      <span className="flex items-center justify-between gap-2">
        {label}
        {hint && <span className="text-right text-[11px] font-bold text-slate-400">{hint}</span>}
      </span>
      <div className="mt-2">{children}</div>
    </label>
  );
}

function ProcessSteps({ steps, progress, activeJob }) {
  const events = (activeJob?.events || []).slice(-6).reverse();
  return (
    <div className="mt-5 rounded-3xl border border-slate-200 bg-slate-50 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-500">Estado del proceso</p>
        <span className="text-xs font-black text-slate-500">{progress}%</span>
      </div>
      <div className="mb-4 h-2 overflow-hidden rounded-full bg-slate-200">
        <div className="h-full rounded-full bg-blue-600 transition-all duration-500" style={{ width: `${progress}%` }} />
      </div>
      <ol className="space-y-3">
        {steps.map((step, index) => (
          <li key={step.label} className="flex items-center gap-3 text-sm font-bold text-slate-700">
            <span className={stepIconClass(step.state)}>{step.state === 'done' ? '✓' : index + 1}</span>
            <span className={step.state === 'done' ? 'text-slate-500 line-through decoration-slate-300' : ''}>{step.label}</span>
          </li>
        ))}
      </ol>
      {events.length > 0 && (
        <div className="mt-4 rounded-2xl bg-white p-3 ring-1 ring-slate-200">
          <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">Últimas actualizaciones</p>
          <div className="mt-2 space-y-2">
            {events.map((event) => (
              <div key={`${event.timestamp}-${event.progress}`} className="text-xs font-semibold text-slate-600">
                <span className="font-black text-slate-900">{event.progress}%</span> · {event.step} · {event.message}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ConfirmItem({ label, value }) {
  return (
    <div>
      <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">{label}</p>
      <p className="mt-1 font-black text-slate-950">{value}</p>
    </div>
  );
}

function ResultMetric({ label, value }) {
  return (
    <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4 text-center">
      <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-400">{label}</p>
      <p className="mt-1 text-3xl font-black text-slate-950">{value}</p>
    </div>
  );
}

function FormatRow({ field, example }) {
  return (
    <tr>
      <td className="px-4 py-3 font-black text-slate-950">{field}</td>
      <td className="px-4 py-3 font-semibold text-slate-600">{example}</td>
    </tr>
  );
}

function buildStepsFromProgress(progress, status = 'running') {
  if (status === 'failed') {
    return baseSteps.map((label, index) => ({ label, state: index === 0 ? 'done' : index === 1 ? 'error' : 'pending' }));
  }
  if (status === 'completed') return baseSteps.map((label) => ({ label, state: 'done' }));

  const thresholds = [5, 25, 65, 82, 95];
  const currentIndex = thresholds.findIndex((threshold) => progress < threshold);
  return baseSteps.map((label, index) => {
    if (currentIndex === -1 || index < currentIndex) return { label, state: 'done' };
    if (index === currentIndex) return { label, state: 'running' };
    return { label, state: 'pending' };
  });
}

function tabClass(active) {
  return active
    ? 'rounded-xl bg-white px-4 py-2.5 text-blue-700 shadow-sm transition'
    : 'rounded-xl px-4 py-2.5 text-slate-500 transition hover:text-slate-900';
}

function stepIconClass(state) {
  const base = 'grid h-7 w-7 shrink-0 place-items-center rounded-full text-xs font-black';
  if (state === 'done') return `${base} bg-emerald-600 text-white`;
  if (state === 'running') return `${base} animate-pulse bg-blue-600 text-white`;
  if (state === 'error') return `${base} bg-rose-600 text-white`;
  return `${base} bg-slate-200 text-slate-500`;
}

function formatBytes(bytes = 0) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}
