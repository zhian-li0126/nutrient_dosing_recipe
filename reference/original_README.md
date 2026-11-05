# Nutrient Solution Calculator

A production-oriented hydroponic nutrient addition calculator with a responsive vanilla frontend and a private FastAPI calculation service.

The browser collects inputs and renders calculated outputs. Fertilizer stoichiometry, candidate formulations, scoring, and nonnegative least-squares optimization remain in the Python backend and are not shipped as browser assets.

## Requirements

- Python 3.10 or newer
- A current `pip`

## Run locally

From the project directory:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). FastAPI serves the frontend and API from the same process, so no separate frontend server or build step is needed.

## Test

With the environment activated:

```bash
pytest
```

The test suite covers the optimizer's main edge cases, unit conversions, input validation, array shape guarantees, sulfate basis, phosphate/potassium coupling, and frontend integration.

## API

`POST /api/calculate`

Example request:

```json
{
  "target": [434, 117.3, 80.2, 24.6, 96, 50],
  "current": [380, 100, 70, 20, 80, 40],
  "reservoir_volume": 80,
  "stock_concentrations": [100, 100, 100, 100, 100, 100]
}
```

Each concentration vector must contain exactly six nonnegative values in this public input order: nitrate, potassium, calcium, magnesium, sulfate, and dihydrogen phosphate. Reservoir volume must be positive. A stock concentration can be `null`; when provided, it must be positive and uses grams of fertilizer per liter of stock solution.

Validation failures use HTTP 422 with a structured error body. Unexpected server failures use a generic HTTP 500 response and do not expose stack traces.

## Configuration

Copy `.env.example` to `.env` for local reference, then export the desired values before starting Uvicorn. The application intentionally does not load environment files itself; Uvicorn can do so explicitly:

```bash
uvicorn backend.main:app --env-file .env
```

- `CORS_ORIGINS`: comma-separated external origins. Leave empty for the recommended same-origin deployment.
- `ENABLE_API_DOCS`: set to `true` to expose `/api/docs` and its OpenAPI schema in a trusted development environment. It is disabled by default.

For a production deployment, place the service behind HTTPS, run Uvicorn through an appropriate process manager or container platform, and set allowed origins narrowly if cross-origin access is needed.

## Project structure

```text
frontend/
  index.html       Calculator interface
  style.css        Responsive scientific UI
  app.js           Input handling and result rendering only
backend/
  main.py          FastAPI routes, static serving, and safe error responses
  models.py        Pydantic request validation
  nutrient_optimizer.py
                    Private optimization engine
  fertilizer_config.py
                    Server-side fertilizer molecular weights
tests/
  test_optimizer.py
```

Only `frontend/` is mounted as static content. Python files are not exposed by the web server.

## Scientific assumptions

- Concentrations are mg/L of the listed ionic species.
- Sulfur input is on a sulfate (`SO4`) basis, not an elemental sulfur basis.
- The optimizer recommends additions only; it does not model removal or dilution.
- Fertilizer ions are assumed to fully dissociate.
- Stock strengths are grams of fertilizer per liter of stock solution.
- Configured fertilizer molecular weights currently represent anhydrous formulas. Confirm product purity and hydration state before dosing.
