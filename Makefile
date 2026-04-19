.PHONY: help up up-d down build rebuild logs logs-backend shell-backend shell-db migrate test lint download-models clean prod-up

help:
	@echo "Project ONYX - Make Targets"
	@echo "============================="
	@echo "make up              - Start all services in foreground"
	@echo "make up-d            - Start all services in background"
	@echo "make down            - Stop all services"
	@echo "make build           - Build Docker images"
	@echo "make rebuild         - Rebuild without cache"
	@echo "make logs            - Stream logs from all services"
	@echo "make logs-backend    - Stream backend logs only"
	@echo "make shell-backend   - Open shell in backend container"
	@echo "make shell-db        - Open PostgreSQL shell"
	@echo "make migrate         - Run Alembic migrations"
	@echo "make test-backend    - Run pytest on backend"
	@echo "make lint-backend    - Run ruff linter on backend"
	@echo "make download-models - Download YOLO model weights"
	@echo "make clean           - Remove all containers and volumes"
	@echo "make prod-up         - Start production stack"

up:
	docker compose up

up-d:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

rebuild:
	docker compose build --no-cache

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

shell-backend:
	docker compose exec backend /bin/bash

shell-db:
	docker compose exec db psql -U onyx -d onyx

migrate:
	docker compose exec backend alembic upgrade head

test-backend:
	docker compose exec backend pytest

lint-backend:
	docker compose exec backend ruff check app/

download-models:
	docker compose exec backend python -c "from ultralytics import YOLO; YOLO('/app/models/yolov8n-pose.pt')"

clean:
	docker compose down -v --remove-orphans
	docker system prune -f

prod-up:
	docker compose -f docker-compose.prod.yml up -d

prod-down:
	docker compose -f docker-compose.prod.yml down

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f
