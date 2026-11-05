"""Write the public API origin for a static frontend deployment.

No third-party packages are required. This script runs during Pages publishing;
Python is not needed in the browser. Empty configuration remains valid for
local/single-host use, but a Pages build requires an explicit HTTPS API origin.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlsplit


def validate_origin(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        raise ValueError(
            "Set the GitHub Actions repository variable API_BASE_URL to your "
            "backend HTTPS origin, such as https://my-calculator.onrender.com."
        )
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path
        or parsed.query
        or parsed.fragment
        or any(character.isspace() for character in value)
    ):
        raise ValueError(
            "API_BASE_URL must be an HTTPS origin with no path, query, "
            "fragment, or credentials. Do not append /api/calculate."
        )
    # Accessing port also validates malformed port values.
    _ = parsed.port
    return value


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default=os.environ.get("API_BASE_URL", ""))
    parser.add_argument("--output", type=Path, default=root / "frontend" / "config.js")
    args = parser.parse_args()
    try:
        origin = validate_origin(args.api_url)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    config = json.dumps({"apiBaseUrl": origin}, ensure_ascii=True, indent=2)
    args.output.write_text(
        "// Generated deployment configuration. This address is public.\n"
        f"window.APP_CONFIG = Object.freeze({config});\n",
        encoding="utf-8",
    )
    print(f"Configured frontend: {args.output}")


if __name__ == "__main__":
    main()
