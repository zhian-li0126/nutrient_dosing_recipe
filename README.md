# Nutrient Solution Calculator

A complete hydroponic nutrient addition calculator with a plain HTML/CSS/JavaScript
interface and a Python/FastAPI calculation service. It runs locally with one
command, can run entirely on a Python host, and includes a GitHub Pages deployment
workflow for the interface.

## About this package

This is a **rebuilt implementation based on the supplied README and configuration
files**. The original frontend, backend, and tests were not supplied. The original
attachments are preserved under `reference/`; this package does not claim to
reproduce an unavailable original optimizer, candidate-scoring method, or layout.

The rebuilt optimizer solves one weighted nonnegative least-squares problem over
six documented anhydrous fertilizer salts. Its complete method and assumptions
are in [METHOD.md](METHOD.md).

## Run locally

Use Python 3.12 (recommended; the declared dependency ranges require at least
Python 3.10). From this directory:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

On Windows PowerShell, replace the activation line with:

```powershell
.venv\Scripts\Activate.ps1
```

Open <http://127.0.0.1:8000>. FastAPI serves both the interface and API. The initial
inputs are examples and become a real calculation only after Calculate additions
is pressed. No calculations are fabricated in the interface.

If activation is unavailable, invoke the environment's Python directly, such as
`.venv/bin/python` on macOS/Linux or `.venv\Scripts\python.exe` on Windows.

## Put the website online

Read [DEPLOY_GITHUB.md](DEPLOY_GITHUB.md) for complete steps.

- **GitHub Pages + Python host:** publish `frontend/` with the included workflow,
  set the GitHub Actions repository variable `API_BASE_URL`, and set the Python
  host's `CORS_ORIGINS` to your Pages origin.
- **One Python host:** deploy this full project to Render or another Python host.
  The default empty `apiBaseUrl` keeps the interface and API on the same origin.

GitHub Pages alone cannot run this FastAPI backend. Installing dependencies in
an Actions workflow does not create a continuously running API server.

To keep Python source private while using a public Pages repository, run:

```bash
python scripts/package_frontend.py
```

The resulting `dist/github-pages-frontend.zip` contains only the interface and
its deployment helper/workflow. Upload that ZIP's extracted contents to a separate
public repository, and keep the complete backend project in a private repository.
Do not upload the ZIP file itself as the website.

## Use the calculator

1. Enter the solution working volume in liters.
2. Enter current and target concentrations for six ions in mg/L of each listed
   ionic species. Use zero for a fresh-water starting concentration when relevant.
3. Enter each stock concentration in grams of that fertilizer per liter of stock,
   or leave it blank to obtain a dry-mass recommendation without a stock volume.
4. Calculate additions. Review fertilizer masses, estimated stock volumes,
   predicted ion concentrations, and any remaining imbalances.

The fertilizer order is calcium nitrate, potassium nitrate, potassium sulfate,
magnesium nitrate, magnesium sulfate, and monopotassium phosphate. Each result
includes all six fertilizers and all six ions, even when the recommended dose is
zero.

## Scientific scope

- Concentrations represent nitrate, potassium, calcium, magnesium, sulfate, and
  dihydrogen phosphate; sulfate and phosphate inputs are not elemental S and P.
- Fertilizer formulas are pure and **anhydrous**. For hydrated or commercial
  products, update `backend/fertilizer_config.py` and validate the composition
  before using the resulting masses.
- The model permits nonnegative additions and does not model removal or dilution.
- Stock volumes are equivalent quantities calculated from fertilizer mass. The
  concentration prediction keeps the entered working volume fixed and does not
  add stock liquid to the tank volume.
- Coupled nutrient contributions can make exact targets unattainable. Review
  the predicted final concentrations rather than assuming an exact match.

## Test

```bash
python -m pytest
```

Tests cover independent nutrient mass balances, feasible formulations, ionic
bases, coupled ions, initial excess, unit conversion, invalid/nonfinite inputs,
CORS, API behavior, and private-source isolation. The GitHub test workflow runs
these checks on Python 3.12. [VALIDATION.md](VALIDATION.md) records the checks
actually performed on this delivered package.

## API

| Route | Purpose |
| --- | --- |
| `GET /api/health` | Service health |
| `GET /api/config` | Public labels, example inputs, and assumptions |
| `POST /api/calculate` | Compute fertilizer additions and final concentrations |

Example request: [examples/request.json](examples/request.json).

The request fields match the supplied README: `target`, `current`,
`reservoir_volume`, and `stock_concentrations`. Ion vectors always have six
entries in nitrate, potassium, calcium, magnesium, sulfate, dihydrogen-phosphate
order. Stock strengths follow the fertilizer order above.

The calculation response contains `ions`, `fertilizers`, `metrics`, `warnings`,
and `assumptions`. Input errors return HTTP 422; unexpected failures return a
generic HTTP 500 message. No Python source is served as a static asset.

## Configuration

| Setting | Where to set it | Meaning |
| --- | --- | --- |
| `apiBaseUrl` | `frontend/config.js` | Empty for same-origin local/single-host mode |
| `API_BASE_URL` | GitHub Actions repository variable | HTTPS API origin used when publishing Pages |
| `CORS_ORIGINS` | Python hosting environment | Comma-separated allowed interface origins |
| `ENABLE_API_DOCS` | Python hosting environment | `true` enables `/api/docs`; default is `false` |

The Python app does not automatically load `.env`. To use the example locally:

```bash
cp .env.example .env
python -m uvicorn backend.main:app --env-file .env
```

## Files

| Location | Contents |
| --- | --- |
| `frontend/` | Interface, styles, client requests, public configuration |
| `backend/` | API, validation, fertilizer chemistry, optimizer |
| `tests/` | Numerical and API tests |
| `.github/workflows/` | Pages publishing and tests |
| `scripts/` | Pages configuration and frontend-only packaging |
| `render.yaml` | Optional backend hosting Blueprint |
| `reference/` | Unchanged supplied files for provenance |
| `DEPLOY_GITHUB.md` | Deployment instructions and troubleshooting |
| `METHOD.md` | Calculation method and scientific assumptions |

No hosting account is created and no website is published by extracting this ZIP.
