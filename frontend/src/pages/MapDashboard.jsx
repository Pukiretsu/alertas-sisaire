import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import ProcessPanel from '../components/ProcessPanel.jsx';
import BogotaMap from '../components/BogotaMap.jsx';
import StationTable from '../components/StationTable.jsx';
import SessionHistory from '../components/SessionHistory.jsx';
import { fetchDemoGeojson } from '../services/api.js';

const EMPTY_RESULT = {
  station_summary: [],
  stations_geojson: null,
};

export default function MapDashboard() {
  // Estado de la Lógica de Negocio
  const [result, setResult] = useState(EMPTY_RESULT);
  const [demoGeojson, setDemoGeojson] = useState(null);
  const [activeProcess, setActiveProcess] = useState('manual');

  // Estado de la Interfaz (Paneles Flotantes)
  const [isPanelOpen, setIsPanelOpen] = useState(false);
  const [isTableOpen, setIsTableOpen] = useState(false);
  const [isSessionsOpen, setIsSessionsOpen] = useState(false);

  useEffect(() => {
    fetchDemoGeojson().then(setDemoGeojson).catch(() => setDemoGeojson(null));
  }, []);

  const geojson = useMemo(
    () => result?.stations_geojson || demoGeojson,
    [result?.stations_geojson, demoGeojson],
  );

  const totalAlerts = Number(result?.declared_alerts || 0);

  return (
    <div className="relative h-screen w-full overflow-hidden bg-slate-950 text-slate-100 font-sans">
      
      {/* 1. MAPA FULL SCREEN (Fondo) */}
      <div className="absolute inset-0 z-0">
        <BogotaMap geojson={geojson} />
      </div>

      {/* Overlay para móviles cuando los paneles están abiertos */}
      {(isPanelOpen || isTableOpen || isSessionsOpen) && (
        <div 
          className="absolute inset-0 z-10 bg-slate-900/40 backdrop-blur-sm transition-all duration-500 lg:hidden"
          onClick={() => { setIsPanelOpen(false); setIsTableOpen(false); setIsSessionsOpen(false); }}
        />
      )}

      {/* 2. CABECERA FLOTANTE (Navegación y Controles) */}
      <header className="absolute left-4 right-4 top-4 z-20 flex items-center justify-between rounded-2xl border border-white/10 bg-slate-900/70 px-5 py-4 shadow-2xl backdrop-blur-xl lg:left-8 lg:right-8 lg:top-6">
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2 text-sm font-bold text-slate-300 transition hover:text-white">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
            <span className="hidden sm:inline">Inicio</span>
          </Link>
          <div className="h-6 w-px bg-white/20"></div>
          <div>
            <h1 className="text-lg font-black tracking-tight text-white md:text-xl">Dashboard Sisaire</h1>
            <p className="text-xs font-semibold text-sky-300">Monitoreo en Vivo</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {totalAlerts > 0 && (
            <span className="hidden sm:inline-flex items-center gap-2 rounded-full border border-rose-500/30 bg-rose-500/20 px-3 py-1.5 text-xs font-black text-rose-300">
              <span className="h-2 w-2 animate-pulse rounded-full bg-rose-500"></span>
              {totalAlerts} Alerta(s)
            </span>
          )}
          <button 
            onClick={() => { setIsTableOpen(!isTableOpen); setIsPanelOpen(false); setIsSessionsOpen(false); }}
            className={`rounded-xl border px-4 py-2 text-sm font-black transition ${isTableOpen ? 'border-sky-500 bg-sky-500 text-white shadow-lg shadow-sky-500/30' : 'border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white'}`}
          >
            Estaciones
          </button>
          <button 
            onClick={() => { setIsSessionsOpen(!isSessionsOpen); setIsPanelOpen(false); setIsTableOpen(false); }}
            className={`rounded-xl border px-4 py-2 text-sm font-black transition ${isSessionsOpen ? 'border-sky-500 bg-sky-500 text-white shadow-lg shadow-sky-500/30' : 'border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white'}`}
          >
            Sesiones
          </button>
          <button 
            onClick={() => { setIsPanelOpen(!isPanelOpen); setIsTableOpen(false); setIsSessionsOpen(false); }}
            className={`rounded-xl border px-4 py-2 text-sm font-black transition ${isPanelOpen ? 'border-sky-500 bg-sky-500 text-white shadow-lg shadow-sky-500/30' : 'border-white/10 bg-white/5 text-slate-300 hover:bg-white/10 hover:text-white'}`}
          >
            Cargar Datos
          </button>
        </div>
      </header>

      {/* 3. PANEL LATERAL: PROCESAMIENTO (Desliza desde la derecha) */}
      <aside className={`absolute bottom-4 right-4 top-24 z-30 w-full max-w-md transition-transform duration-500 ease-[cubic-bezier(0.4,0,0.2,1)] lg:bottom-6 lg:right-8 lg:top-28 ${isPanelOpen ? 'translate-x-0' : 'pointer-events-none translate-x-[120%]'}`}>
        <div className="no-scrollbar flex h-full w-full flex-col overflow-y-auto">
          <ProcessPanel 
            result={result} 
            setResult={setResult} 
            activeProcess={activeProcess} 
            setActiveProcess={setActiveProcess} 
          />
        </div>
      </aside>

      {/* 4. PANEL DE DATOS: TABLA (Desliza desde la izquierda) */}
      <aside className={`absolute bottom-4 left-4 right-4 z-30 transition-transform duration-500 ease-[cubic-bezier(0.4,0,0.2,1)] lg:bottom-6 lg:left-8 lg:right-auto lg:top-28 lg:w-full lg:max-w-4xl ${isTableOpen ? 'translate-y-0 lg:translate-x-0' : 'pointer-events-none translate-y-[120%] lg:-translate-x-[120%]'}`}>
        <div className="no-scrollbar h-full max-h-[70vh] w-full overflow-y-auto lg:max-h-full">
          <StationTable rows={result?.station_summary || []} />
        </div>
      </aside>

      {/* 5. PANEL DE SESIONES: historial separado de ejecuciones */}
      <aside className={`absolute bottom-4 left-4 right-4 z-30 transition-transform duration-500 ease-[cubic-bezier(0.4,0,0.2,1)] lg:bottom-6 lg:left-8 lg:right-auto lg:top-28 lg:w-full lg:max-w-3xl ${isSessionsOpen ? 'translate-y-0 lg:translate-x-0' : 'pointer-events-none translate-y-[120%] lg:-translate-x-[120%]'}`}>
        <div className="no-scrollbar h-full max-h-[70vh] w-full overflow-y-auto lg:max-h-full">
          <SessionHistory onLoadResult={(sessionResult) => { setResult(sessionResult); setIsSessionsOpen(false); }} />
        </div>
      </aside>

    </div>
  );
}
