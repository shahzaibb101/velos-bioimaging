import type { NextConfig } from "next";

/* The reconstruction service runs as its own process (its own container in
   production). Proxying it under the same origin keeps the browser free of
   CORS preflights on every poll, and means the frontend never needs to know
   the backend's address. */
const API = process.env.VELOS_API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Traced standalone build, for a small runtime image.
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};

export default nextConfig;
