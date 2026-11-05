"""Create an allowlisted frontend repository ZIP without Python service source.

Run from any directory: python scripts/package_frontend.py
Extract the result and upload its CONTENTS to the public frontend repository.
"""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


FRONTEND_README = """# Nutrient calculator: GitHub Pages interface

This repository contains the browser interface. The Python calculator is
deployed separately; no optimizer code is included here.

## Publish

1. Deploy the complete Python project from its private repository.
2. In that service, set CORS_ORIGINS to https://YOUR-ACCOUNT.github.io
   (use your real account; exclude the repository path and trailing slash).
3. In this repository, open Settings > Secrets and variables > Actions >
   Variables and add API_BASE_URL with the backend HTTPS origin, for example
   https://my-calculator.onrender.com. Exclude /api/calculate.
4. Open Settings > Pages and choose GitHub Actions as the publishing source.
5. Push to main, or run Publish calculator frontend from Actions manually.
6. Open the Pages URL and click Calculate additions. If you later change the
   repository variable, run the workflow again to update the deployed files.

The address in config.js is public configuration. The workflow generates it
from API_BASE_URL during deployment. Do not put secrets in frontend files.

The calculator uses ionic species (NO3, K, Ca, Mg, SO4, H2PO4) in mg/L and
assumes pure anhydrous fertilizer salts. Stock strengths are g of fertilizer
per L of stock. It models additions to a fixed working volume, not dilution.

Use a trusted hosting service for the API and retain the private backend's
complete project and instructions. The Pages workflow publishes frontend/
only and does not install or run the backend.
"""


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    members = [
        "frontend/index.html",
        "frontend/style.css",
        "frontend/app.js",
        "frontend/config.js",
        "frontend/.nojekyll",
        ".github/workflows/deploy-pages.yml",
        "scripts/configure_frontend.py",
    ]
    missing = [name for name in members if not (root / name).is_file()]
    if missing:
        raise SystemExit("Missing required files: " + ", ".join(missing))
    output = root / "dist" / "github-pages-frontend.zip"
    output.parent.mkdir(exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name in members:
            archive.write(root / name, arcname=name)
        archive.writestr("README.md", FRONTEND_README)
        archive.writestr(".gitignore", ".DS_Store\n__pycache__/\n*.py[cod]\n.env\n")
    print(output)


if __name__ == "__main__":
    main()
