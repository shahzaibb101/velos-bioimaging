export interface Sample {
  slug: string; title: string; blurb: string; exposure: string;
  photons: number; size: number; field_um: number; cells: number;
  median_dry_mass_pg: number | null;
}

export interface Scores {
  psnr_db?: number; ssim?: number; rmse_rad?: number; correlation?: number;
  mass_median_abs_pct?: number; mass_bias_pct?: number; mass_cells?: number;
}

export interface Method {
  name: string; label: string; milliseconds: number; detail: string;
  range_rad: [number, number]; scores?: Scores;
}

export interface Cell {
  label: number; centroid_x_um: number; centroid_y_um: number; area_um2: number;
  mean_phase_rad: number; max_phase_rad: number; dry_mass_pg: number;
  circularity: number; rounded: boolean;
}

export interface JobResult {
  optics: Record<string, number>;
  field: { pixels: [number, number]; micrometres: [number, number] };
  reconstructions: Method[];
  primary: string;
  cell_count: number;
  total_dry_mass_pg: number;
  median_dry_mass_pg: number | null;
  has_ground_truth: boolean;
  display_range_rad: [number, number];
  layers: string[];
  cells: Cell[];
  disagreement?: { mean_rad: number; max_rad: number; p99_rad: number };
  notes: string[];
}

export interface Job {
  id: string; state: "queued" | "running" | "done" | "failed";
  progress: number; stage: string; created: string;
  request: { source: string; label: string; pixels: [number, number] };
  error: string | null; result: JobResult | null;
}

const json = async <T,>(res: Response): Promise<T> => {
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
};

export const getSamples = () => fetch("/api/samples").then(json<Sample[]>);
export const getHealth = () => fetch("/api/health").then(json<Record<string, unknown>>);
export const getJob = (id: string) => fetch(`/api/jobs/${id}`).then(json<Job>);

export const submitSample = (slug: string) => {
  const body = new FormData();
  body.append("sample", slug);
  return fetch("/api/jobs", { method: "POST", body }).then(json<Job>);
};

export const submitUpload = (file: File) => {
  const body = new FormData();
  body.append("file", file);
  return fetch("/api/jobs", { method: "POST", body }).then(json<Job>);
};

export const layerUrl = (id: string, name: string) => `/api/jobs/${id}/layers/${name}.png`;
export const cellsCsvUrl = (id: string) => `/api/jobs/${id}/cells.csv`;
export const phaseTiffUrl = (id: string) => `/api/jobs/${id}/phase.tif`;
