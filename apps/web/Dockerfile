# Build context is the repo root (see infra/docker-compose.yml). This image
# is for local `docker compose up` dev use only - the Vercel deploy builds
# apps/web directly with its own Next.js build pipeline, not this file.
FROM node:20-slim

WORKDIR /workspace/app

COPY apps/web/package.json ./
RUN npm install

COPY apps/web .

EXPOSE 3000
CMD ["npm", "run", "dev"]
