.PHONY: streamlit install up down seed seed-local run test eval lint
PY = .venv/bin/python

streamlit:      ## interface Streamlit (API attendue sur :8000)
	$(PY) -m streamlit run streamlit_app/app.py

install:        ## environnement local
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

up:             ## base + application (http://localhost:8000)
	docker compose up --build -d

down:
	docker compose down

seed:           ## données de démo dans le conteneur (--reset : repart de zéro)
	docker compose exec app python -m app.seed --reset

run:            ## lancement local (DATABASE_URL du .env, SQLite par défaut)
	$(PY) -m alembic upgrade head && $(PY) -m uvicorn app.main:app --reload

seed-local:     ## schéma + données de démo en local
	$(PY) -m alembic upgrade head && $(PY) -m app.seed --reset

test:
	$(PY) -m pytest -q

eval:           ## évaluation de l'assistant (fournisseur = LLM_PROVIDER)
	$(PY) -m eval.run_eval

lint:
	$(PY) -m ruff format --check . && $(PY) -m ruff check .
