.PHONY: backend-install backend-test backend-format calculate-demo api frontend-install frontend-dev frontend-build frontend-preview clean-generated

backend-install:
	cd backend && python -m pip install -e ".[dev]" && playwright install chromium

backend-test:
	cd backend && PYTHONPATH=src pytest

backend-format:
	cd backend && black src tests && ruff check src tests --fix

calculate-demo:
	cd backend && air-quality-alerts calculate --input ../data/samples/ejemplo_pm25_bogota.csv --output ../outputs/memoria_demo.csv --excel-output ../outputs/memoria_demo.xlsx

api:
	cd backend && air-quality-alerts api

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

frontend-preview:
	cd frontend && npm run preview

clean-generated:
	rm -rf outputs/* downloads/* backend/.pytest_cache backend/.ruff_cache frontend/.vite
	touch outputs/.gitkeep downloads/.gitkeep
