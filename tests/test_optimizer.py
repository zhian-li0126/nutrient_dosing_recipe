"""Regression tests for the server-side nutrient calculation engine."""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.nutrient_optimizer import ELEMENT_MOLAR_MASS, calculate_nutrient_addition


DEFAULT_TARGET = np.array([434.0, 117.3, 80.2, 24.6, 96.0, 50.0])
EXAMPLE_CURRENT = np.array([380.0, 100.0, 70.0, 20.0, 80.0, 40.0])
NO_STOCKS: list[float | None] = [None] * 6


def calculate(
    target: np.ndarray = DEFAULT_TARGET,
    current: np.ndarray | None = None,
    volume: float = 80.0,
    stocks: list[float | None] | None = None,
) -> dict:
    return calculate_nutrient_addition(
        target=target,
        current=np.zeros(6) if current is None else current,
        reservoir_volume_l=volume,
        stock_concentrations=NO_STOCKS if stocks is None else stocks,
    )


def test_all_current_concentrations_equal_zero() -> None:
    result = calculate()

    assert len(result["nutrients"]) == 6
    assert all(item["current_mg_L"] == 0 for item in result["nutrients"])
    assert any(item["mass_g"] > 0 for item in result["fertilizers"])


def test_current_equals_target_requires_no_fertilizer() -> None:
    result = calculate(current=DEFAULT_TARGET.copy())

    assert all(item["mmol_L"] == pytest.approx(0.0) for item in result["fertilizers"])
    assert [item["final_mg_L"] for item in result["nutrients"]] == pytest.approx(
        DEFAULT_TARGET
    )


def test_nutrient_above_target_is_not_directly_removed() -> None:
    current = EXAMPLE_CURRENT.copy()
    current[0] = DEFAULT_TARGET[0] + 20.0
    result = calculate(current=current)

    nitrate = result["nutrients"][0]
    assert nitrate["requested_increase_mg_L"] == 0.0
    assert nitrate["final_mg_L"] >= current[0]
    assert any(
        warning["type"] == "above_target" and warning["nutrient"] == "NO3"
        for warning in result["warnings"]
    )


def test_omitted_stock_concentrations_return_null_volumes() -> None:
    result = calculate(current=EXAMPLE_CURRENT)

    assert all(item["stock_volume_ml"] is None for item in result["fertilizers"])
    assert any(warning["type"] == "missing_stock" for warning in result["warnings"])


def test_valid_eighty_liter_reservoir_mass_and_stock_conversion() -> None:
    result = calculate(current=EXAMPLE_CURRENT, stocks=[100.0] * 6)

    assert result["reservoir_volume_L"] == 80.0
    for fertilizer in result["fertilizers"]:
        assert fertilizer["mass_g"] == pytest.approx(
            fertilizer["mg_L"] * 80.0 / 1000.0
        )
        assert fertilizer["stock_volume_ml"] == pytest.approx(
            fertilizer["mass_g"] / 100.0 * 1000.0
        )


def test_negative_input_is_rejected_by_api() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        "/api/calculate",
        json={
            "target": DEFAULT_TARGET.tolist(),
            "current": [-1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "reservoir_volume": 80.0,
            "stock_concentrations": NO_STOCKS,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_fertilizer_amounts_cannot_be_negative() -> None:
    result = calculate(current=EXAMPLE_CURRENT)

    assert all(item["mmol_L"] >= 0 for item in result["fertilizers"])
    assert all(item["mass_g"] >= 0 for item in result["fertilizers"])


def test_result_arrays_always_have_six_elements() -> None:
    result = calculate(current=EXAMPLE_CURRENT)

    assert len(result["nutrients"]) == 6
    assert len(result["fertilizers"]) == 6


def test_sulfate_uses_ionic_molecular_weight_not_elemental_sulfur() -> None:
    assert ELEMENT_MOLAR_MASS[4] == 96.0
    assert ELEMENT_MOLAR_MASS[4] != 32.0


def test_monopotassium_phosphate_contributes_potassium() -> None:
    phosphate_target = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 97.0])
    result = calculate(target=phosphate_target)

    kh2po4_mmol_l = result["fertilizers"][5]["mmol_L"]
    predicted_potassium_mg_l = result["nutrients"][1]["predicted_increase_mg_L"]
    assert kh2po4_mmol_l > 0
    assert predicted_potassium_mg_l == pytest.approx(kh2po4_mmol_l * 39.0)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target", [0.0] * 5),
        ("current", [0.0] * 7),
        ("stock_concentrations", [None] * 5),
    ],
)
def test_api_requires_exactly_six_vector_values(field: str, value: list) -> None:
    client = TestClient(app, raise_server_exceptions=False)
    payload = {
        "target": DEFAULT_TARGET.tolist(),
        "current": [0.0] * 6,
        "reservoir_volume": 80.0,
        "stock_concentrations": [None] * 6,
    }
    payload[field] = value

    response = client.post("/api/calculate", json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_zero_reservoir_and_zero_stock_are_rejected() -> None:
    client = TestClient(app, raise_server_exceptions=False)
    payload = {
        "target": DEFAULT_TARGET.tolist(),
        "current": [0.0] * 6,
        "reservoir_volume": 0.0,
        "stock_concentrations": [0.0, None, None, None, None, None],
    }

    response = client.post("/api/calculate", json=payload)

    assert response.status_code == 422


def test_frontend_and_security_headers_are_served() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "Nutrient Solution Calculator" in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_private_optimizer_files_are_not_static_assets() -> None:
    client = TestClient(app)

    response = client.get("/static/nutrient_optimizer.py")

    assert response.status_code == 404
    frontend_javascript = client.get("/static/app.js").text.lower()
    for private_term in ("candidate_indices", "column_stack", "nnls", "weights"):
        assert private_term not in frontend_javascript
