.PHONY: help setup run scheduler lint format session docker docker-up

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup: ## Create venv and install all deps
	python3 -m venv .venv
	.venv/bin/pip install -e ".[all,dev]"
	mkdir -p data
	cp -n .env.example .env 2>/dev/null || true
	@echo "Edit .env with your credentials, then run: make run"

run: ## Run the bot
	.venv/bin/python -m src.main

scheduler: ## Run scheduler once
	.venv/bin/python -m src.scheduler_main

lint: ## Lint with ruff
	.venv/bin/ruff check src/

format: ## Auto-format with ruff
	.venv/bin/ruff format src/

session: ## Generate Telethon session string
	.venv/bin/python generate_session.py

docker: ## Build Docker image
	docker compose build

docker-up: ## Start bot in Docker
	docker compose up -d bot
