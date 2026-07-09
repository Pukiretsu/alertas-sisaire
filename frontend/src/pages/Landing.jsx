import { Link } from 'react-router-dom';

export default function Landing() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#020617] bg-[radial-gradient(circle_at_top_left,_rgba(59,130,246,0.38),_transparent_34%),radial-gradient(circle_at_80%_0%,_rgba(14,165,233,0.20),_transparent_30%),linear-gradient(135deg,_#020617_0%,_#0f172a_45%,_#172554_100%)] px-6 text-slate-100">
      
      {/* Elementos decorativos de fondo */}
      <div className="absolute left-10 top-1/4 h-72 w-72 rounded-full bg-blue-500/10 blur-3xl" />
      <div className="absolute bottom-1/4 right-10 h-96 w-96 rounded-full bg-sky-500/10 blur-3xl" />

      <section className="relative z-10 mx-auto max-w-5xl text-center">
        <div className="mb-8 inline-flex items-center gap-3 rounded-full border border-sky-300/20 bg-sky-300/10 px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-sky-200 shadow-lg shadow-sky-900/20 backdrop-blur-md">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sky-400 opacity-75"></span>
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-sky-500"></span>
          </span>
          Sistema de Alertas Ambientales
        </div>
        
        <h1 className="mb-6 text-5xl font-black tracking-tight text-white drop-shadow-xl md:text-7xl lg:text-8xl">
          Monitoreo de <span className="bg-gradient-to-r from-sky-400 to-blue-600 bg-clip-text text-transparent">Calidad del Aire</span>
        </h1>
        
        <p className="mx-auto mb-12 max-w-2xl text-lg font-medium leading-relaxed text-slate-300 md:text-xl">
          Plataforma analítica en tiempo real para visualizar, procesar y consolidar las alertas de prevención y emergencia reportadas por las estaciones.
        </p>
        
        <div className="flex flex-col items-center justify-center gap-5 sm:flex-row">
          <Link to="/map" className="btn-hero-primary px-8 py-4 text-base shadow-sky-500/20">
            Abrir Mapa Interactivo
          </Link>
          <a href="https://github.com/tu-repo" target="_blank" rel="noreferrer" className="btn-hero-secondary px-8 py-4 text-base">
            Ver Documentación
          </a>
        </div>
      </section>
    </main>
  );
}
