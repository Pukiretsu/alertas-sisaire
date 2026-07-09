const API_BASE = import.meta.env.VITE_API_BASE_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '');

export function resultUrl(path) {
  if (!path) return '#';
  if (path.startsWith('http')) return path;
  return `${API_BASE}${path}`;
}

export async function fetchDemoGeojson() {
  const response = await fetch('/stations_sisaire_car.geojson');
  if (!response.ok) throw new Error('No fue posible cargar el catálogo GeoJSON de estaciones.');
  return response.json();
}

export async function fetchStationsCatalog() {
  return apiFetch('/api/stations/catalog');
}

export async function fetchStationsList() {
  return apiFetch('/api/stations');
}

export async function calculateAirQuality({ file, pollutant, minReadings }) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('pollutant', pollutant);
  formData.append('min_valid_readings_24h', String(minReadings));

  return apiFetch('/api/calculate', {
    method: 'POST',
    body: formData,
  });
}

export async function createCalculationJob({ file, pollutant, minReadings }) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('pollutant', pollutant);
  formData.append('min_valid_readings_24h', String(minReadings));

  return apiFetch('/api/jobs/calculate', {
    method: 'POST',
    body: formData,
  });
}

export async function runAutoSampling(payload) {
  return apiFetch('/api/auto-sampling', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function createAutoSamplingJob(payload) {
  return apiFetch('/api/jobs/auto-sampling', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

export async function fetchJob(jobId) {
  return apiFetch(`/api/jobs/${jobId}`);
}

export async function fetchJobs(limit = 25) {
  return apiFetch(`/api/jobs?limit=${limit}`);
}

async function apiFetch(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || 'No fue posible completar la solicitud.');
  }
  return payload;
}
