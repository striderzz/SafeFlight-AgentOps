.PHONY: up down logs test lint fmt web-check

up:          ## full stack: redis, MCP servers, api, web
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api safety-data live-signals

lint:
	ruff check . && ruff format --check .

fmt:
	ruff format . && ruff check --fix .

test: lint   ## unit and integration tests with FakeLLM; no API key needed
	pytest

web-check:   ## typecheck and production build of the web app
	cd web && npm ci && npx tsc --noEmit && npm run build
