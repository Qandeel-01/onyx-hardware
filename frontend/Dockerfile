FROM node:20-alpine

WORKDIR /app

RUN apk add --no-cache curl

COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# Browser talks to API on host :8000; env set in docker-compose (VITE_* read when Vite starts).
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS http://127.0.0.1:5173/ >/dev/null || exit 1
