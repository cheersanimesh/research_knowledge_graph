.PHONY: help build up down logs shell exec-query exec-ingest clean

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Build the Docker image
	docker-compose build

up: ## Start all services
	docker-compose up -d

down: ## Stop all services
	docker-compose down

down-volumes: ## Stop services and remove volumes (⚠️ deletes database data)
	docker-compose down -v

logs: ## Show logs from all services
	docker-compose logs -f

logs-app: ## Show logs from app service
	docker-compose logs -f app

logs-db: ## Show logs from database service
	docker-compose logs -f postgres

shell: ## Open a shell in the app container
	docker-compose exec app /bin/bash

db-shell: ## Open a PostgreSQL shell
	docker-compose exec postgres psql -U postgres -d paper_graph_db

init-db: ## Initialize database schema
	docker-compose exec -T postgres psql -U postgres -d paper_graph_db < sql/schema.sql
	docker-compose exec -T postgres psql -U postgres -d paper_graph_db < sql/init_pgvector.sql

exec-query: ## Run a query command (usage: make exec-query ARGS="query papers")
	docker-compose exec app python src/main.py $(ARGS)

exec-ingest: ## Ingest papers (usage: make exec-ingest FILE=src/examples/sample_papers.json)
	docker-compose exec app python src/main.py ingest $(FILE)

clean: ## Remove containers, networks, and images
	docker-compose down --rmi all --volumes --remove-orphans

restart: ## Restart all services
	docker-compose restart

status: ## Show status of all services
	docker-compose ps

