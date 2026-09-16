import type { Metadata } from "next";
import Reconstructor from "@/components/app/Reconstructor";

export const metadata: Metadata = {
  title: "Reconstruct",
  description:
    "Run a live-cell acquisition through the Velos pipeline: physics reconstruction, learned refinement, and per-cell dry mass.",
};

export default function Page() {
  return <Reconstructor />;
}
