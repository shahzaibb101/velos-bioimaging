"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Viewer from "./Viewer";
import Container from "@/components/Container";
import HeaderTheme from "@/components/HeaderTheme";
import {
  Job, Sample, getJob, getSamples, layerUrl, submitSample, submitUpload,
  cellsCsvUrl, phaseTiffUrl,
} from "@/lib/api";

const LAYER_LABELS: Record<string, string> = {
  raw: "Camera, at focus",
  "raw-under": "Camera, under focus",
  "raw-over": "Camera, over focus",
  tie: "Transport of intensity",
  waveorder: "waveorder",
  model: "Physics-guided model",
  truth: "Ground truth",
  disagreement: "Model minus physics",
  outlines: "Segmented cells",
};

const POLL_MS = 900;

export default function Reconstructor() {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [left, setLeft] = useState("raw");
  const [right, setRight] = useState("model");
  const timer = useRef<number | null>(null);

  useEffect(() => {
    getSamples().then(setSamples).catch((e) => setError(e.message));
    return () => { if (timer.current) window.clearTimeout(timer.current); };
  }, []);

  /* Poll until the job settles. setTimeout rather than setInterval so a slow
     response can never stack requests on top of each other. */
  const poll = useCallback((id: string) => {
    const tick = async () => {
      try {
        const next = await getJob(id);
        setJob(next);
        if (next.state === "done") {
          setBusy(false);
          const layers = next.result?.layers ?? [];
          setLeft("raw");
          setRight(layers.includes("model") ? "model" : "tie");
        } else if (next.state === "failed") {
          setBusy(false);
          setError(next.error ?? "The reconstruction failed.");
        } else {
          timer.current = window.setTimeout(tick, POLL_MS);
        }
      } catch (e) {
        setBusy(false);
        setError((e as Error).message);
      }
    };
    tick();
  }, []);

  const start = async (run: () => Promise<Job>) => {
    setError(null); setBusy(true); setJob(null);
    try {
      const created = await run();
      setJob(created);
      poll(created.id);
    } catch (e) {
      setBusy(false);
      setError((e as Error).message);
    }
  };

  const result = job?.state === "done" ? job.result : null;
  const layers = result?.layers ?? [];

  return (
    <div className="app">
      <HeaderTheme surface="dark" />
      <Container>
        <header className="app__head">
          <span className="label">Reconstruction</span>
          <h1 className="app__title">Run the pipeline.</h1>
          <p className="app__lead">
            Pick an acquisition and watch it go through the whole instrument: three camera
            planes in, a calibrated phase map and a per-cell mass table out. Every number
            below is computed on the spot, not stored.
          </p>
        </header>

        <section className="app__sources" aria-label="Choose an acquisition">
          <div className="app__samples">
            {samples.map((s) => (
              <button
                key={s.slug}
                className="sample"
                disabled={busy}
                onClick={() => start(() => submitSample(s.slug))}
              >
                <span className="sample__title">{s.title}</span>
                <span className="sample__blurb">{s.blurb}</span>
                <span className="sample__meta">
                  {s.cells} cells · {s.field_um} µm field · {s.photons.toLocaleString()} photons
                </span>
              </button>
            ))}
          </div>

          <label className="upload">
            <input
              type="file"
              accept=".tif,.tiff"
              disabled={busy}
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) start(() => submitUpload(file));
                e.target.value = "";
              }}
            />
            <span className="upload__title">Or upload your own stack</span>
            <span className="upload__hint">
              A 3-plane 16-bit TIFF ordered under focus, in focus, over focus.
            </span>
          </label>
        </section>

        {error && <p className="app__error" role="alert">{error}</p>}

        {job && job.state !== "done" && !error && (
          <div className="progress" role="status" aria-live="polite">
            <div className="progress__bar"><span style={{ transform: `scaleX(${job.progress})` }} /></div>
            <p className="progress__stage">
              {job.stage}
              <span className="progress__pct">{Math.round(job.progress * 100)}%</span>
            </p>
          </div>
        )}

        {result && (
          <>
            <div className="app__viewer">
              <Viewer
                left={layerUrl(job!.id, left)}
                right={layerUrl(job!.id, right)}
                leftLabel={LAYER_LABELS[left] ?? left}
                rightLabel={LAYER_LABELS[right] ?? right}
                alt={`Reconstruction of ${job!.request.label}`}
              />
              <div className="app__layers">
                {(["left", "right"] as const).map((side) => (
                  <div key={side} className="app__layerpick">
                    <span className="app__layerlabel">{side === "left" ? "Left panel" : "Right panel"}</span>
                    <div className="chips">
                      {layers.map((name) => (
                        <button
                          key={name}
                          className={`chip ${(side === "left" ? left : right) === name ? "is-active" : ""}`}
                          onClick={() => (side === "left" ? setLeft(name) : setRight(name))}
                        >
                          {LAYER_LABELS[name] ?? name}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <Colorbar range={result.display_range_rad} />
            </div>

            <Scorecard result={result} />

            {result.disagreement && (
              <p className="app__note">
                The model departs from the physics by {result.disagreement.mean_rad.toFixed(3)} rad on
                average and {result.disagreement.p99_rad.toFixed(2)} rad at the 99th percentile. Compare
                the two directly with the <em>Model minus physics</em> layer: a correction concentrated
                on the cells and their background is the classical solver&rsquo;s known bias being undone,
                whereas structure appearing where the physics saw none would be the model inventing it.
              </p>
            )}

            <CellTable result={result} jobId={job!.id} />
          </>
        )}
      </Container>
    </div>
  );
}

function Colorbar({ range }: { range: [number, number] }) {
  return (
    <div className="colorbar">
      <span className="colorbar__tick">{range[0].toFixed(2)}</span>
      <span className="colorbar__ramp" aria-hidden="true" />
      <span className="colorbar__tick">{range[1].toFixed(2)}</span>
      <span className="colorbar__unit">radians</span>
    </div>
  );
}

function Scorecard({ result }: { result: NonNullable<Job["result"]> }) {
  const truth = result.has_ground_truth;
  return (
    <section className="scorecard">
      <table>
        <caption>
          {truth
            ? "Scored against ground truth, which exists because the specimen was defined before it was imaged."
            : "No ground truth for an uploaded stack, so only timings and ranges are shown."}
        </caption>
        <thead>
          <tr>
            <th scope="col">Method</th>
            <th scope="col">Time</th>
            {truth && <><th scope="col">Correlation</th><th scope="col">RMSE</th>
              <th scope="col">PSNR</th><th scope="col">Dry mass error</th></>}
          </tr>
        </thead>
        <tbody>
          {result.reconstructions.map((m) => (
            <tr key={m.name} className={m.name === result.primary ? "is-primary" : ""}>
              <th scope="row">
                {m.label}
                <span className="scorecard__detail">{m.detail}</span>
              </th>
              <td>{m.milliseconds < 1000 ? `${Math.round(m.milliseconds)} ms` : `${(m.milliseconds / 1000).toFixed(1)} s`}</td>
              {truth && (
                <>
                  <td>{m.scores?.correlation?.toFixed(3) ?? "—"}</td>
                  <td>{m.scores?.rmse_rad?.toFixed(3) ?? "—"} rad</td>
                  <td>{m.scores?.psnr_db?.toFixed(1) ?? "—"} dB</td>
                  <td>{m.scores?.mass_median_abs_pct?.toFixed(1) ?? "—"}%</td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function CellTable({ result, jobId }: { result: NonNullable<Job["result"]>; jobId: string }) {
  const [all, setAll] = useState(false);
  const rows = all ? result.cells : result.cells.slice(0, 12);
  return (
    <section className="cells">
      <header className="cells__head">
        <div>
          <h2 className="cells__title">{result.cell_count} cells measured</h2>
          <p className="cells__sub">
            {result.total_dry_mass_pg.toLocaleString()} pg total, median{" "}
            {result.median_dry_mass_pg?.toFixed(0)} pg per cell.
          </p>
        </div>
        <div className="cells__actions">
          <a className="chip" href={cellsCsvUrl(jobId)} download>Download CSV</a>
          <a className="chip" href={phaseTiffUrl(jobId)} download>Phase map (32-bit TIFF)</a>
        </div>
      </header>
      <div className="cells__scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">#</th><th scope="col">Position</th><th scope="col">Area</th>
              <th scope="col">Mean phase</th><th scope="col">Dry mass</th><th scope="col">Shape</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.label}>
                <td>{c.label}</td>
                <td>{c.centroid_x_um.toFixed(0)}, {c.centroid_y_um.toFixed(0)} µm</td>
                <td>{c.area_um2.toFixed(0)} µm²</td>
                <td>{c.mean_phase_rad.toFixed(2)} rad</td>
                <td className="is-figure">{c.dry_mass_pg.toFixed(1)} pg</td>
                <td>{c.rounded ? "rounded" : "spread"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {result.cells.length > 12 && (
        <button className="chip" onClick={() => setAll((v) => !v)}>
          {all ? "Show fewer" : `Show all ${result.cells.length}`}
        </button>
      )}
    </section>
  );
}
