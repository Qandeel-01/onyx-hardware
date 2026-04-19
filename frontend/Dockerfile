# ── Stage 1: dependencies ────────────────────────────────────────
FROM node:20-alpine AS deps

WORKDIR /app
COPY package*.json ./
RUN npm ci

# ── Stage 2: dev (hot-reload, source mounted as volume) ───────────
FROM node:20-alpine AS dev

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV VITE_API_BASE_URL="http://localhost:8000"
ENV VITE_WS_URL="ws://localhost:8000"

EXPOSE 5173
CMD ["npm", "run", "dev"]

# ── Stage 3: production build ─────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

ENV VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://localhost:8000}"
ENV VITE_WS_URL="${VITE_WS_URL:-ws://localhost:8000}"

RUN npm run build

# ── Stage 4: production (nginx) ───────────────────────────────────
FROM nginx:1.25-alpine AS prod

COPY nginx.frontend.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
