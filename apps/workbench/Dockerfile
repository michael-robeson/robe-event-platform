FROM node:22-slim AS ui
WORKDIR /ui
COPY apps/workbench/ui/package.json apps/workbench/ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/workbench/ui/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY --from=ui /ui/dist ./ui/dist
CMD ["uvicorn", "robe_event_platform.workbench.server:app", "--host", "0.0.0.0", "--port", "8000"]
