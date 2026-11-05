# Package validation

Prepared on October 29, 2026.

## Completed checks

- **39 automated tests passed** in 6.37 seconds using `python -m pytest`.
- Independent reference mass balances confirm nutrient units and feasible mixtures.
- Tested no-deficit/zero-dose behavior, initial excess, coupled ions, sulfate and
  phosphate species bases, optional stock strengths, and volume scaling.
- Tested six-entry vectors, negative/null/nonfinite input, malformed JSON,
  extreme finite input, request-size limits, and safe error responses.
- Tested allowed and unlisted cross-origin requests, API documentation disabled
  by default, static asset serving, and Python-source isolation.
- JavaScript syntax checked with `node --check`.
- HTML checked for duplicate IDs, referenced labels, relative assets, and
  configuration loading before the application script.
- Parsed both GitHub workflow YAML files and the Render Blueprint.
- Pages configuration helper accepted a valid HTTPS origin and rejected five
  missing or malformed origins.
- Frontend-only archive inspected for private backend files.
- ZIP integrity and included source-file contents verified before delivery.

## Test environment

| Component | Version |
| --- | --- |
| Python | 3.12.14 |
| FastAPI | 0.162.0 |
| Starlette | 1.10.0 |
| Uvicorn | 0.54.0 |
| NumPy | 2.3.5 |
| SciPy | 1.17.0 |
| Pydantic | 2.14.1 |
| pytest | 9.2.0 |
| httpx2 | 2.16.0 |

The original uploaded `requirements.txt` works unchanged in this environment.
Installed Starlette's TestClient supports httpx2. No substitution of the package
name with httpx was necessary.

## Limits of verification

This package was not published to a GitHub or Render account. Actual deployment
still needs the user's API origin, Pages origin, account settings, and a live
site check. YAML syntax checks do not substitute for running the workflows in
those accounts.

Visual browser rendering was not completed: a test-browser download was
unavailable in this environment. HTML/JavaScript checks and real ASGI API tests
passed; no screenshot-based layout verification is claimed.

Numerical tests validate the implemented equations and units. They do not
validate fertilizer product composition or agronomic suitability. The model
assumes pure anhydrous salts, fixed volume, and additions only.

No comparison with the original application's code or tests was possible,
because those files were not supplied. See README.md for reconstruction scope.
