.PHONY: setup keys build up down migrate init-operator dev-backend dev-frontend

# Generate RSA keys
keys:
	python scripts/setup/generate_rsa_keys.py keys/private.pem keys/public.pem

# Initialize first operator
init-operator:
	cd backend/api && python ../../scripts/setup/init_operator.py

# Run database migrations
migrate:
	cd backend/api && alembic upgrade head

# Docker compose
up:
	docker-compose up --build -d

down:
	docker-compose down -v

# Development servers (requires local postgres + redis)
dev-backend:
	cd backend/api && uvicorn app.main:app --reload --port 8000

dev-frontend:
	cd frontend && npm install && npm run dev

# Setup everything for local dev
setup: keys
	@echo "1. Start postgres + redis (docker-compose up -d postgres redis)"
	@echo "2. Run: make migrate"
	@echo "3. Run: make init-operator"
	@echo "4. Run: make dev-backend (in one terminal)"
	@echo "5. Run: make dev-frontend (in another terminal)"
