import { NextRequest } from "next/server";

/**
 * Runtime proxy to the reconstruction service.
 *
 * This exists instead of a `next.config` rewrite because rewrites are resolved
 * during `next build` and baked into the standalone output. In a container the
 * build does not see the service environment, so the destination silently
 * becomes whatever the fallback was — which works perfectly in development and
 * fails on every request in production.
 *
 * A route handler runs per request, so the address is read when it is actually
 * needed. Keeping the browser same-origin also means no CORS preflight on the
 * poll loop, which fires every 900ms while a job runs.
 */

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const upstream = () =>
  (process.env.VELOS_API_URL ?? "http://127.0.0.1:8000").replace(/\/+$/, "");

/** Headers worth carrying back: content type, disposition, caching. */
const PASS_THROUGH = ["content-type", "content-disposition", "cache-control", "content-length"];

async function forward(request: NextRequest, path: string[]) {
  const search = request.nextUrl.search;
  const target = `${upstream()}/api/${path.join("/")}${search}`;

  const init: RequestInit = {
    method: request.method,
    headers: (() => {
      const headers = new Headers();
      const type = request.headers.get("content-type");
      if (type) headers.set("content-type", type);
      const accept = request.headers.get("accept");
      if (accept) headers.set("accept", accept);
      return headers;
    })(),
    // Streaming the body through is what keeps multipart uploads working
    // without buffering the whole file into memory first.
    body: request.method === "GET" || request.method === "HEAD"
      ? undefined
      : await request.arrayBuffer(),
    cache: "no-store",
  };

  try {
    const response = await fetch(target, init);
    const headers = new Headers();
    for (const name of PASS_THROUGH) {
      const value = response.headers.get(name);
      if (value) headers.set(name, value);
    }
    return new Response(response.body, { status: response.status, headers });
  } catch (error) {
    // A reconstruction service that is still waking up should read as a
    // service problem, not as a broken page.
    return Response.json(
      {
        detail: "The reconstruction service is not reachable right now.",
        upstream: target.replace(/^(https?:\/\/[^/]+).*$/, "$1"),
        cause: (error as Error).message,
      },
      { status: 502 }
    );
  }
}

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return forward(request, (await context.params).path);
}

export async function POST(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  return forward(request, (await context.params).path);
}
