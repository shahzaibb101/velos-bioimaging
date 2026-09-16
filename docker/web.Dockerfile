# Marketing site and reconstruction UI.
FROM node:22-slim AS deps
WORKDIR /app
COPY web/package.json web/package-lock.json* ./
RUN npm ci

FROM node:22-slim AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

# Next resolves rewrites at build time and bakes them into the standalone
# output, so the API address has to be present *here*, not only at runtime.
# A Docker build does not inherit the service environment, so it has to arrive
# as a build argument or the proxy silently falls back to localhost and every
# API call 500s in production while working perfectly in development.
ARG VELOS_API_URL
ENV VELOS_API_URL=${VELOS_API_URL}

COPY --from=deps /app/node_modules ./node_modules
COPY web ./
RUN npm run build

FROM node:22-slim AS runtime
WORKDIR /app
# HOSTNAME matters. Next's standalone server binds to os.hostname() when this
# is unset, which inside a container is the container id, so the process listens
# on an address the platform's proxy cannot reach and every request returns 502
# despite the deploy reporting success.
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
# Next's standalone output carries only the traced dependencies, which is a
# fraction of node_modules and makes cold starts noticeably quicker.
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["sh", "-c", "node server.js"]
