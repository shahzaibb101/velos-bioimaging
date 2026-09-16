/**
 * Velos BioImaging mark.
 *
 * Three wavefronts crossing a circular field, the middle one retarded as it
 * passes through the specimen. That lag is the entire physical basis of
 * quantitative phase imaging, so the mark states what the instrument measures
 * rather than decorating around it.
 *
 * Single colour, driven by --logo-fill so it can invert over dark sections.
 */
export function LogoMark({ size = 21 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" fill="none" aria-hidden="true">
      <circle cx="14" cy="14" r="12.6" stroke="currentColor" strokeWidth="1.7" />
      <path d="M7.4 4.6C9.9 8.3 9.9 19.7 7.4 23.4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <path d="M13.6 3.1C17.6 7.6 17.6 20.4 13.6 24.9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      <path d="M20.2 4.6C22.7 8.3 22.7 19.7 20.2 23.4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}

export default function Logo() {
  return (
    <span className="logo">
      <LogoMark />
      <span className="logo__word">
        Velos<span className="logo__word-light">Bio</span>
      </span>
    </span>
  );
}
