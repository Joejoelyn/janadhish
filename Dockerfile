FROM node:22-alpine AS web-build
WORKDIR /web
COPY web/package*.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt ./
RUN pip install --no-cache-dir --progress-bar off -r requirements.txt
COPY backend ./backend
COPY frontend ./frontend
COPY alembic.ini ./
COPY migrations ./migrations
COPY --from=web-build /web/dist ./web/dist
CMD ["sh", "-c", "python -m backend.manage_schema && uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
