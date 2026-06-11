export default function StatusBadge({ status = 'Sin dato', compact = false }) {
  const value = String(status || 'Sin dato').toLowerCase();
  let className = 'border-slate-200 bg-slate-100 text-slate-700';

  if (value.includes('normal')) className = 'border-emerald-200 bg-emerald-100 text-emerald-800';
  if (value.includes('prev')) className = 'border-amber-200 bg-amber-100 text-amber-900';
  if (value.includes('alerta')) className = 'border-rose-200 bg-rose-100 text-rose-800';
  if (value.includes('emerg')) className = 'border-red-950 bg-red-950 text-white';

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border font-black ${compact ? 'px-2.5 py-1 text-[11px]' : 'px-3 py-1.5 text-xs'} ${className}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {status || 'Sin dato'}
    </span>
  );
}
