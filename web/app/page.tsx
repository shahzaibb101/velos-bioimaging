import Hero from "@/components/blocks/Hero";
import Statement from "@/components/blocks/Statement";
import Cards from "@/components/blocks/Cards";
import Marquee from "@/components/blocks/Marquee";
import Button from "@/components/Button";
import { IconWavefront, IconNetwork, IconMeasure } from "@/components/Icons";

const CAPABILITIES = [
  {
    index: "01.",
    heading: "Physics reconstruction",
    text: "A partially coherent model of the instrument, inverted. Three frames at different focus, one calibrated phase map, in about sixteen milliseconds.",
    icon: <IconWavefront />,
    tone: "light" as const,
  },
  {
    index: "02.",
    heading: "Learned refinement",
    text: "A network that corrects the physics rather than replacing it. It starts as the solver and only moves where the correction measurably helps.",
    icon: <IconNetwork />,
    tone: "dark" as const,
  },
  {
    index: "03.",
    heading: "Per-cell measurement",
    text: "Cells separated, then measured. Area, thickness and dry mass in picograms for every cell in the field, exported as a table you can analyse.",
    icon: <IconMeasure />,
    tone: "light" as const,
  },
];

export default function Home() {
  return (
    <>
      <Hero />

      <Statement
        label="The instrument"
        className="section--bone"
        heading={<>Optics, physics and deep learning in one reconstruction pipeline, <em>on a microscope you can afford.</em></>}
        action={<Button href="/platform" label="How it works" />}
      >
        <p>
          Commercial quantitative phase systems cost more than most labs will ever
          spend on one instrument. We replaced the expensive optics with computation:
          ordinary brightfield frames at three focal planes, a wave-optical model of
          the microscope, and a reconstruction that returns physical units rather
          than grey levels.
        </p>
      </Statement>

      <Cards cards={CAPABILITIES} />

      <Marquee text="Label-free · quantitative · live-cell" accent="—" />

      <Statement
        label="Honestly"
        split
        ascent={false}
        heading={<>What this demo is, <em>and what it is not.</em></>}
      >
        <p>
          Everything here runs. The physics, the reconstruction, the network and the
          measurements are real code producing real output. The specimens are
          simulated, because a simulator is the only way to obtain ground truth, and
          without ground truth no reconstruction claim can be checked. Point it at
          real microscope data and the pipeline is unchanged.
        </p>
      </Statement>
    </>
  );
}
