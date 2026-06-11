import { useEffect } from 'react';

export default function Modal({ open, title, eyebrow, children, footer, onClose, size = 'md' }) {
  useEffect(() => {
    if (!open) return undefined;

    function handleKeyDown(event) {
      if (event.key === 'Escape') onClose?.();
    }

    document.body.classList.add('overflow-hidden');
    window.addEventListener('keydown', handleKeyDown);

    return () => {
      document.body.classList.remove('overflow-hidden');
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [open, onClose]);

  if (!open) return null;

  const widthClass = size === 'lg' ? 'max-w-4xl' : size === 'sm' ? 'max-w-lg' : 'max-w-2xl';

  return (
    <div
      className="fixed inset-0 z-[9999] grid place-items-center bg-slate-950/70 px-4 py-6 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose?.();
      }}
    >
      <section className={`max-h-[90vh] w-full ${widthClass} overflow-hidden rounded-[2rem] border border-white/20 bg-white text-slate-900 shadow-2xl`}>
        <header className="flex items-start justify-between gap-4 border-b border-slate-200 bg-gradient-to-r from-slate-50 to-blue-50 px-6 py-5">
          <div>
            {eyebrow && <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-600">{eyebrow}</p>}
            <h2 id="modal-title" className="mt-1 text-2xl font-black tracking-tight text-slate-950">
              {title}
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="grid h-10 w-10 shrink-0 place-items-center rounded-full border border-slate-200 bg-white text-xl font-black text-slate-500 shadow-sm transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900"
            aria-label="Cerrar modal"
          >
            ×
          </button>
        </header>

        <div className="max-h-[62vh] overflow-y-auto px-6 py-5">{children}</div>

        {footer && <footer className="border-t border-slate-200 bg-slate-50 px-6 py-4">{footer}</footer>}
      </section>
    </div>
  );
}
