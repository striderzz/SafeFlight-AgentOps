# Next.js standalone build: a small runtime image with only the server output.
FROM node:20-alpine AS build
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web ./
RUN npm run build

FROM node:20-alpine
LABEL org.opencontainers.image.source="https://github.com/striderzz/SafeFlight-AgentOps" \
      org.opencontainers.image.description="SafeFlight web app"
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
WORKDIR /app
COPY --from=build /web/.next/standalone ./
COPY --from=build /web/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
