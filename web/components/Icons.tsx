/**
 * Card icons, drawn as dense line art in the same idiom as the reference:
 * thin uniform strokes, geometric construction, no fills.
 *
 * Each one is generated rather than hand-plotted, because the density that
 * makes these read as instrument diagrams (60+ strokes) is not something to
 * maintain by hand.
 */

const S = 114;
const C = S / 2;
const stroke = { stroke: "currentColor", strokeWidth: 0.9, strokeMiterlimit: 10, fill: "none" } as const;

/** Wavefronts converging through a lens: the forward model. */
export function IconWavefront() {
  const arcs = Array.from({ length: 13 }, (_, i) => {
    const x = 6 + i * 8.5;
    const bulge = 26 * Math.sin((i / 12) * Math.PI);
    return `M${x} 8C${x + bulge} 30 ${x + bulge} 84 ${x} 106`;
  });
  return (
    <svg viewBox={`0 0 ${S} ${S}`} {...stroke} aria-hidden="true">
      <circle cx={C} cy={C} r={53} {...stroke} />
      {arcs.map((d, i) => <path key={i} d={d} {...stroke} />)}
    </svg>
  );
}

/** A network folded over a residual path: the learned correction. */
export function IconNetwork() {
  const layers = [4, 6, 6, 4];
  const nodes = layers.flatMap((count, col) =>
    Array.from({ length: count }, (_, row) => ({
      x: 12 + col * 30,
      y: C + (row - (count - 1) / 2) * 17,
      col,
    }))
  );
  const edges: string[] = [];
  for (let col = 0; col < layers.length - 1; col++) {
    nodes.filter((n) => n.col === col).forEach((a) =>
      nodes.filter((n) => n.col === col + 1).forEach((b) =>
        edges.push(`M${a.x} ${a.y}L${b.x} ${b.y}`)
      )
    );
  }
  return (
    <svg viewBox={`0 0 ${S} ${S}`} {...stroke} aria-hidden="true">
      {edges.map((d, i) => <path key={i} d={d} {...stroke} opacity={0.45} />)}
      {nodes.map((n, i) => <circle key={i} cx={n.x} cy={n.y} r={2.6} {...stroke} />)}
      <path d={`M12 ${C - 46}C56 ${C - 52} 58 ${C + 52} 102 ${C + 46}`} {...stroke} />
    </svg>
  );
}

/** Cells on a measurement grid: per-cell readout. */
export function IconMeasure() {
  const grid = Array.from({ length: 11 }, (_, i) => 7 + i * 10);
  const cells = [
    { x: 34, y: 38, r: 15 }, { x: 72, y: 46, r: 11 },
    { x: 46, y: 76, r: 13 }, { x: 82, y: 82, r: 8 },
  ];
  return (
    <svg viewBox={`0 0 ${S} ${S}`} {...stroke} aria-hidden="true">
      {grid.map((v, i) => <path key={`h${i}`} d={`M7 ${v}H107`} {...stroke} opacity={0.25} />)}
      {grid.map((v, i) => <path key={`v${i}`} d={`M${v} 7V107`} {...stroke} opacity={0.25} />)}
      {cells.map((c, i) => (
        <g key={i}>
          <circle cx={c.x} cy={c.y} r={c.r} {...stroke} />
          <circle cx={c.x} cy={c.y} r={c.r * 0.42} {...stroke} />
          <path d={`M${c.x - c.r} ${c.y + c.r + 4}H${c.x + c.r}`} {...stroke} />
        </g>
      ))}
    </svg>
  );
}
