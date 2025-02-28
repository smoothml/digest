.DEFAULT_GOAL := help
SHELL := /bin/bash

.PHONY: help
help: ## Show all available commands
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST);

.PHONY: mypy
mypy: ## Run mypy type checking
	@uv run mypy src tests;

.PHONY: ruff
ruff: ## Run ruff linting checks
	@uv run ruff check src tests;

.PHONY: ruff-fix
ruff-fix: ## Fix linting and formatting with Ruff
	@uv run ruff check --fix src tests;
	@uv run ruff format src tests;

.PHONY: test
test: ## Run tests
	@uv run pytest tests;