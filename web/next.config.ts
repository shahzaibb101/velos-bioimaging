import type { NextConfig } from "next";

/* No API rewrite here on purpose. Rewrites resolve at build time and get baked
   into the standalone output, so in a container they capture whatever the build
   environment knew rather than what the service is configured with at runtime.
   app/api/[...path]/route.ts proxies instead, reading the address per request. */
const nextConfig: NextConfig = {
  // Traced standalone build, for a small runtime image.
  output: "standalone",
};

export default nextConfig;
