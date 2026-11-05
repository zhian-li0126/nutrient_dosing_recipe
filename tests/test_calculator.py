"""Behavioral checks for physical units, constrained dosing, and deployment.

The reference chemistry below is independent of the application matrix.  Tests
check ion mass balance instead of requiring a unique fertilizer formulation:
multiple nonnegative blends can produce the same ionic composition.
"""

from __future__ import annotations

import json
import math

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


ION_IDS = [
    "nitrate", "potassium", "calcium", "magnesium", "sulfate",
    "dihydrogen_phosphate",
]

# Standard rounded atomic weights in g/mol; independent of backend imports.
ION_MASSES = [62.004, 39.0983, 40.078, 24.305, 96.056, 96.985762]
SALT_ION_COUNTS = [
    [2, 0, 1, 0, 0, 0],  # Ca(NO3)2
    [1, 1, 0, 0, 0, 0],  # KNO3
    [0, 2, 0, 0, 1, 0],  # K2SO4
    [2, 0, 0, 1, 0, 0],  # Mg(NO3)2
    [0, 0, 0, 1, 1, 0],  # MgSO4
    [0, 1, 0, 0, 0, 1],  # KH2PO4
]


def reference_additions(grams, volume_l):
    """Convert weighed anhydrous salts into ionic mg/L by mass conservation."""
    added = [0.0] * 6
    for fertilizer_g, counts in zip(grams, SALT_ION_COUNTS):
        salt_molar_mass = sum(n * m for n, m in zip(counts, ION_MASSES))
        moles = fertilizer_g / salt_molar_mass
        for i, count in enumerate(counts):
            added[i] += moles * count * ION_MASSES[i] * 1000 / volume_l
    return added


@pytest.fixture
def payload():
    return {
        "target": [434, 117.3, 80.2, 24.6, 96, 50],
        "current": [380, 100, 70, 20, 80, 40],
        "reservoir_volume": 80,
        "stock_concentrations": [100] * 6,
    }


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://example.github.io")
    monkeypatch.delenv("ENABLE_API_DOCS", raising=False)
    with TestClient(create_app()) as api:
        yield api


def calculate(client, payload):
    response = client.post("/api/calculate", json=payload)
    assert response.status_code == 200, response.text
    # Reject nonstandard JSON NaN/Infinity even if a parser would tolerate it.
    result = json.loads(
        response.text,
        parse_constant=lambda value: pytest.fail(f"Non-finite JSON: {value}"),
    )
    assert len(result["ions"]) == len(result["fertilizers"]) == 6
    assert [ion["id"] for ion in result["ions"]] == ION_IDS
    return result


def test_health_and_public_metadata(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    response = client.get("/api/config")
    assert response.status_code == 200
    metadata = response.json()
    assert len(metadata["ions"]) == len(metadata["fertilizers"]) == 6
    assert [ion["id"] for ion in metadata["ions"]] == ION_IDS
    assert "stoichiometry" not in metadata
    assert "composition_matrix" not in metadata


@pytest.mark.parametrize("concentrations", [[0] * 6, [100, 50, 20, 10, 40, 5]])
def test_no_deficit_requires_no_fertilizer(client, payload, concentrations):
    payload["target"] = concentrations
    payload["current"] = concentrations
    result = calculate(client, payload)
    assert [item["grams"] for item in result["fertilizers"]] == pytest.approx([0] * 6)
    assert [item["final"] for item in result["ions"]] == pytest.approx(concentrations)
    assert result["metrics"]["rmse_mg_l"] == pytest.approx(0)
    if concentrations == [0] * 6:
        assert all(item["relative_error_percent"] is None for item in result["ions"])


def test_existing_excess_is_not_removed(client, payload):
    payload["target"] = [10] * 6
    payload["current"] = [20, 30, 40, 50, 60, 70]
    result = calculate(client, payload)
    assert [item["grams"] for item in result["fertilizers"]] == pytest.approx([0] * 6)
    assert [item["final"] for item in result["ions"]] == pytest.approx(payload["current"])
    assert result["warnings"]


def test_signed_excess_is_part_of_optimization(client, payload):
    # Adding nitrate to fill potassium would worsen a large existing excess.
    payload["target"] = [1, 100, 0, 0, 0, 0]
    payload["current"] = [100, 0, 0, 0, 0, 0]
    result = calculate(client, payload)
    initial_cost = sum(
        ((current - target) / max(target, 1)) ** 2
        for current, target in zip(payload["current"], payload["target"])
    )
    final_cost = sum(
        ((item["final"] - target) / max(target, 1)) ** 2
        for item, target in zip(result["ions"], payload["target"])
    )
    assert final_cost <= initial_cost + 1e-8
    assert result["ions"][0]["added"] == pytest.approx(0, abs=1e-8)


def test_feasible_blend_preserves_mass_and_matches_targets(client, payload):
    volume = 80
    known_grams = [10, 5, 3, 2, 4, 1]
    current = [10, 5, 3, 1, 2, 0.5]
    additions = reference_additions(known_grams, volume)
    payload.update(
        current=current,
        target=[c + a for c, a in zip(current, additions)],
        reservoir_volume=volume,
    )
    result = calculate(client, payload)
    grams = [item["grams"] for item in result["fertilizers"]]
    assert all(math.isfinite(value) and value >= 0 for value in grams)
    predicted_additions = reference_additions(grams, volume)
    assert [item["added"] for item in result["ions"]] == pytest.approx(
        predicted_additions, rel=1e-5, abs=1e-5
    )
    assert [item["final"] for item in result["ions"]] == pytest.approx(
        payload["target"], rel=1e-5, abs=1e-5
    )


@pytest.mark.parametrize("volume, expected_grams", [(80, 10), (160, 20)])
def test_phosphate_potassium_coupling_and_stock_volume(client, payload, volume, expected_grams):
    # Ten grams of KH2PO4 in 80 L supplies both K+ and H2PO4-, not elemental P.
    target = reference_additions([0, 0, 0, 0, 0, 10], 80)
    payload.update(target=target, current=[0] * 6, reservoir_volume=volume)
    result = calculate(client, payload)
    assert [item["final"] for item in result["ions"]] == pytest.approx(target, rel=1e-5, abs=1e-5)
    dose = result["fertilizers"][5]
    assert dose["grams"] == pytest.approx(expected_grams, rel=1e-5)
    assert dose["stock_volume_ml"] == pytest.approx(expected_grams * 10, rel=1e-5)
    assert result["ions"][1]["added"] / result["ions"][5]["added"] == pytest.approx(
        ION_MASSES[1] / ION_MASSES[5], rel=1e-5
    )


def test_sulfate_basis_is_not_elemental_sulfur(client, payload):
    target = reference_additions([0, 0, 0, 0, 5, 0], 80)
    payload.update(target=target, current=[0] * 6)
    result = calculate(client, payload)
    assert result["fertilizers"][4]["grams"] == pytest.approx(5, rel=1e-5)
    assert result["ions"][4]["added"] / result["ions"][3]["added"] == pytest.approx(
        96.056 / 24.305, rel=1e-5
    )


def test_unknown_stock_strength_keeps_grams_but_omits_volume(client, payload):
    payload["stock_concentrations"] = [None] * 6
    result = calculate(client, payload)
    assert all(item["stock_volume_ml"] is None for item in result["fertilizers"])
    assert sum(item["grams"] for item in result["fertilizers"]) > 0


@pytest.mark.parametrize(
    "field, value",
    [
        ("target", [1] * 5),
        ("current", [1] * 7),
        ("stock_concentrations", [100] * 5),
        ("target", [-1, 0, 0, 0, 0, 0]),
        ("current", [None, 0, 0, 0, 0, 0]),
        ("target", [True, 0, 0, 0, 0, 0]),
        ("stock_concentrations", [0, 100, 100, 100, 100, 100]),
        ("stock_concentrations", [-1, 100, 100, 100, 100, 100]),
        ("reservoir_volume", 0),
        ("reservoir_volume", -1),
        ("reservoir_volume", None),
    ],
)
def test_invalid_input_returns_validation_error(client, payload, field, value):
    payload[field] = value
    response = client.post("/api/calculate", json=payload)
    assert response.status_code == 422, response.text
    assert response.headers["content-type"].startswith("application/json")
    assert "detail" in response.json()
    assert "Traceback" not in response.text


@pytest.mark.parametrize("bad_value", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_input_has_safe_json_error(client, payload, bad_value):
    payload["target"][0] = bad_value
    response = client.post(
        "/api/calculate", content=json.dumps(payload),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422, response.text
    json.loads(response.text, parse_constant=lambda value: pytest.fail(value))
    assert "Traceback" not in response.text


def test_malformed_json_returns_validation_error(client):
    response = client.post(
        "/api/calculate", content='{"target":',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert "detail" in response.json()


def test_extreme_but_finite_values_return_validation_error(client, payload):
    payload["reservoir_volume"] = 1e308
    payload["stock_concentrations"] = [1e-300] * 6
    response = client.post("/api/calculate", json=payload)
    assert response.status_code == 422, response.text
    json.loads(response.text, parse_constant=lambda value: pytest.fail(value))


def test_oversize_calculation_body_is_rejected(client):
    response = client.post(
        "/api/calculate", content=b" " * (64 * 1024 + 1),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_internal_failure_does_not_expose_traceback(client, payload, monkeypatch):
    def fail_calculation(_request):
        raise RuntimeError("INTERNAL_TEST_SENTINEL")

    monkeypatch.setattr("backend.main.calculate_nutrients", fail_calculation)
    response = client.post("/api/calculate", json=payload)
    assert response.status_code == 500
    assert "detail" in response.json()
    assert "INTERNAL_TEST_SENTINEL" not in response.text
    assert "Traceback" not in response.text


def test_cross_origin_json_post_preflight(client, payload):
    origin = "https://example.github.io"
    preflight = client.options(
        "/api/calculate",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200, preflight.text
    assert preflight.headers["access-control-allow-origin"] == origin
    actual = client.post("/api/calculate", json=payload, headers={"Origin": origin})
    assert actual.status_code == 200
    assert actual.headers["access-control-allow-origin"] == origin


def test_unlisted_origin_has_no_cors_permission(client):
    response = client.options(
        "/api/calculate",
        headers={
            "Origin": "https://unlisted.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(
    "path", ["/backend/main.py", "/backend/nutrient_optimizer.py", "/.env", "/requirements.txt"]
)
def test_private_project_files_are_not_static_assets(client, path):
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("path", ["/api/docs", "/api/openapi.json", "/docs", "/openapi.json"])
def test_api_docs_are_disabled_by_default(client, path):
    assert client.get(path).status_code == 404


def test_frontend_and_configuration_are_served(client):
    page = client.get("/")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    for path in ["/style.css", "/config.js", "/app.js"]:
        response = client.get(path)
        assert response.status_code == 200, path

