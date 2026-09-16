import type { Metadata } from "next";
import Statement from "@/components/blocks/Statement";
import Cards from "@/components/blocks/Cards";
import Button from "@/components/Button";
import Container from "@/components/Container";
import { IconWavefront, IconNetwork, IconMeasure } from "@/components/Icons";

export const metadata: Metadata = {
  title: "Platform",
  description:
    "How Velos reconstructs quantitative phase from ordinary brightfield frames: a wave-optical model of the instrument, a learned correction, and per-cell dry mass.",
};

const STAGES = [
  {
    index: "01.",
    heading: "Acquire",
    text: "Three brightfield frames at different focus. No dye, no fluorescence, no excitation light, and nothing added to the sample.",
    icon: <IconWavefront />,
    tone: "light" as const,
  },
  {
    index: "02.",
    heading: "Reconstruct",
    text: "A wave-optical model of the microscope, inverted. The result is phase in radians, not a grey level, so it means the same thing on any instrument.",
    icon: <IconNetwork />,
    tone: "dark" as const,
  },
  {
    index: "03.",
    heading: "Measure",
    text: "Cells separated and measured. Dry mass follows from phase by a constant that has been known since the 1950s.",
    icon: <IconMeasure />,
    tone: "light" as const,
  },
];

export default function Platform() {
  return (
    <>
      <section className="section section--bone page-hero">
        <Container>
          <span className="label">Platform</span>
          <h1 className="page-hero__title">
            A microscope measures intensity. <em>The information is in the delay.</em>
          </h1>
          <p className="page-hero__lead">
            Light passing through a cell comes out behind the light that went around it, because
            the cell is optically denser than the medium. That lag is the cell&rsquo;s whole
            structure, and a camera discards it. Reconstructing it is the entire product.
          </p>
        </Container>
      </section>

      <Cards cards={STAGES} />

      <Statement
        label="Reconstruction"
        heading={<>Three methods run on every job, <em>and all three are shown.</em></>}
        action={<Button href="/reconstruct" label="Run it yourself" />}
      >
        <p>
          A single reconstruction is a claim. Three that agree are evidence. Every job runs the
          classical Transport of Intensity solve, the published waveorder inverse from CZ Biohub,
          and a learned refinement, and reports where they disagree rather than quietly picking
          one. The learned model predicts a correction to the physics and its final layer is
          initialised at zero, so before training it reproduces the classical solver exactly.
        </p>
      </Statement>

      <Statement
        label="Measurement"
        split
        ascent={false}
        heading={<>Phase in radians. Mass in picograms. <em>Nothing in arbitrary units.</em></>}
      >
        <p>
          The recovered phase at each pixel is proportional to the optical path length through the
          specimen, which is proportional to the dry mass of material there. That makes the output
          a measurement rather than a picture: a cell&rsquo;s mass in picograms, tracked over hours,
          without ever touching it.
        </p>
      </Statement>
    </>
  );
}
