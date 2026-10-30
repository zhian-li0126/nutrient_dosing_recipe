"""Private nutrient optimization and unit-conversion engine.

This module is imported by the API server and is never mounted as a static asset.
All arrays use the ion order [NO3, K, Ca, Mg, SO4, H2PO4].
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
from scipy.optimize import nnls

from backend.fertilizer_config import COMPOUND_MOLAR_MASS, FERTILIZER_NAMES


NUTRIENT_NAMES: tuple[str, ...] = ("NO3", "K", "Ca", "Mg", "SO4", "H2PO4")
NUTRIENT_DISPLAY_NAMES: tuple[str, ...] = (
    "NO3−",
    "K+",
    "Ca2+",
    "Mg2+",
    "SO4²−",
    "H2PO4−",
)

K = 39.0
CA = 40.0
MG = 24.0
NO3 = 62.0
SO4 = 96.0
H2PO4 = 97.0

ELEMENT_MOLAR_MASS = np.array([NO3, K, CA, MG, SO4, H2PO4], dtype=float)

CaNO3 = np.array([2, 0, 1, 0, 0, 0], dtype=float)
KNO3 = np.array([1, 1, 0, 0, 0, 0], dtype=float)
K2SO4 = np.array([0, 2, 0, 0, 1, 0], dtype=float)
MgNO3 = np.array([2, 0, 0, 1, 0, 0], dtype=float)
MgSO4 = np.array([0, 0, 0, 1, 1, 0], dtype=float)
KH2PO4 = np.array([0, 1, 0, 0, 0, 1], dtype=float)

ALL_COMPOUNDS = [CaNO3, KNO3, K2SO4, MgNO3, MgSO4, KH2PO4]

CANDIDATE_INDICES = [
    [0, 2, 3, 5],
    [0, 1, 2, 3, 5],
    [0, 1, 4, 5],
    [0, 1, 2, 4, 5],
    [0, 2, 3, 4, 5],
    [0, 1, 3, 4, 5],
    [0, 1, 2, 3, 4, 5],
]

WEIGHTS = np.array([4, 4, 2, 2, 2, 2], dtype=float)
MAXIMUM_REWARD = int(np.sum(WEIGHTS))
ZERO_TOLERANCE = 1e-12


def _as_six_value_array(values: Sequence[float], field_name: str) -> np.ndarray:
    """Defensively validate direct calls made outside the API layer."""
    array = np.asarray(values, dtype=float)
    if array.shape != (6,):
        raise ValueError(f"{field_name} must contain exactly six values")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{field_name} must contain only finite values")
    if np.any(array < 0):
        raise ValueError(f"{field_name} cannot contain negative values")
    return array


def _select_best_candidate(delta_mmol: np.ndarray) -> dict[str, Any]:
    """Select the highest-reward formulation, breaking ties by weighted error."""
    best_indices: list[int] | None = None
    best_matrix: np.ndarray | None = None
    best_solution: np.ndarray | None = None
    best_prediction: np.ndarray | None = None
    best_reward = -1.0
    best_error = float("inf")

    for indices in CANDIDATE_INDICES:
        matrix = np.column_stack([ALL_COMPOUNDS[index] for index in indices])
        solution, _residual = nnls(matrix, delta_mmol)
        prediction = matrix @ solution

        denominator = np.maximum(delta_mmol, 1e-9)
        relative_error = np.abs(prediction - delta_mmol) / denominator
        reward = float(np.sum(WEIGHTS[relative_error <= 0.15]))
        weighted_error = float(np.sum(WEIGHTS * relative_error**2))

        if reward > best_reward or (
            reward == best_reward and weighted_error < best_error
        ):
            best_indices = list(indices)
            best_matrix = matrix
            best_solution = solution
            best_prediction = prediction
            best_reward = reward
            best_error = weighted_error

    if (
        best_indices is None
        or best_matrix is None
        or best_solution is None
        or best_prediction is None
    ):
        raise RuntimeError("No fertilizer candidate could be selected")

    return {
        "indices": best_indices,
        "matrix": best_matrix,
        "solution": best_solution,
        "prediction": best_prediction,
        "reward": best_reward,
        "weighted_error": best_error,
    }


def _build_warnings(
    current: np.ndarray,
    target: np.ndarray,
    final_concentration: np.ndarray,
    stock_concentrations: Sequence[float | None],
) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []

    for index, nutrient_name in enumerate(NUTRIENT_NAMES):
        if current[index] > target[index]:
            warnings.append(
                {
                    "type": "above_target",
                    "nutrient": nutrient_name,
                    "message": (
                        f"{nutrient_name} is already above the target concentration. "
                        "No direct addition was requested for this ion, but coupled "
                        "fertilizers may still increase its concentration."
                    ),
                }
            )

        noticeable_overshoot = max(target[index] * 0.05, 1.0)
        if final_concentration[index] > target[index] + noticeable_overshoot:
            warnings.append(
                {
                    "type": "coupled_overshoot",
                    "nutrient": nutrient_name,
                    "message": (
                        f"Predicted {nutrient_name} concentration is above the "
                        "requested target because fertilizer salts can supply "
                        "multiple ions."
                    ),
                }
            )

    if any(value is None for value in stock_concentrations):
        warnings.append(
            {
                "type": "missing_stock",
                "nutrient": "",
                "message": (
                    "Stock solution concentration was not provided for one or more "
                    "fertilizers. Dry fertilizer mass is shown instead."
                ),
            }
        )

    return warnings


def calculate_nutrient_addition(
    target: np.ndarray | Sequence[float],
    current: np.ndarray | Sequence[float],
    reservoir_volume_l: float,
    stock_concentrations: list[float | None],
) -> dict[str, Any]:
    """Calculate a nonnegative fertilizer recommendation.

    Concentrations are mg/L of each listed ion. Optimizer quantities are mmol/L;
    fertilizer mass conversions use the configured anhydrous g/mol values.
    """
    target_array = _as_six_value_array(target, "target")
    current_array = _as_six_value_array(current, "current")

    if not np.isfinite(reservoir_volume_l) or reservoir_volume_l <= 0:
        raise ValueError("reservoir_volume_l must be a positive finite number")
    if len(stock_concentrations) != 6:
        raise ValueError("stock_concentrations must contain exactly six values")
    for value in stock_concentrations:
        if value is not None and (not np.isfinite(value) or value <= 0):
            raise ValueError(
                "stock concentrations must be positive finite values when provided"
            )

    delta_ppm = np.maximum(target_array - current_array, 0.0)
    delta_mmol = delta_ppm / ELEMENT_MOLAR_MASS

    selected = _select_best_candidate(delta_mmol)
    best_indices: list[int] = selected["indices"]
    best_solution: np.ndarray = selected["solution"]
    best_prediction: np.ndarray = selected["prediction"]

    mols_to_add = np.zeros(6, dtype=float)
    for local_index, fertilizer_index in enumerate(best_indices):
        mols_to_add[fertilizer_index] = best_solution[local_index]

    # Remove floating-point noise without altering scored optimizer values.
    mols_to_add[np.abs(mols_to_add) < ZERO_TOLERANCE] = 0.0
    if np.any(mols_to_add < 0):
        raise RuntimeError("The optimizer returned a negative fertilizer amount")

    fertilizer_mg_per_l = mols_to_add * COMPOUND_MOLAR_MASS
    mass_g = fertilizer_mg_per_l * float(reservoir_volume_l) / 1000.0

    predicted_delta_mg_l = best_prediction * ELEMENT_MOLAR_MASS
    final_concentration = current_array + predicted_delta_mg_l
    denominator = np.maximum(delta_mmol, 1e-9)
    relative_error = np.abs(best_prediction - delta_mmol) / denominator

    nutrient_results = []
    for index, name in enumerate(NUTRIENT_NAMES):
        final_fit_tolerance_mg_l = max(target_array[index] * 0.05, 1.0)
        nutrient_results.append(
            {
                "name": name,
                "display_name": NUTRIENT_DISPLAY_NAMES[index],
                "current_mg_L": float(current_array[index]),
                "target_mg_L": float(target_array[index]),
                "requested_increase_mg_L": float(delta_ppm[index]),
                "predicted_increase_mg_L": float(predicted_delta_mg_l[index]),
                "difference_mg_L": float(predicted_delta_mg_l[index] - delta_ppm[index]),
                "final_mg_L": float(final_concentration[index]),
                "relative_error_percent": float(relative_error[index] * 100.0),
                "fit_status": (
                    "close"
                    if abs(final_concentration[index] - target_array[index])
                    <= final_fit_tolerance_mg_l
                    else "outside"
                ),
            }
        )

    fertilizer_results = []
    for index, name in enumerate(FERTILIZER_NAMES):
        stock_concentration = stock_concentrations[index]
        stock_volume_ml = (
            None
            if stock_concentration is None
            else float(mass_g[index] / stock_concentration * 1000.0)
        )
        fertilizer_results.append(
            {
                "name": name,
                "mmol_L": float(mols_to_add[index]),
                "mg_L": float(fertilizer_mg_per_l[index]),
                "mass_g": float(mass_g[index]),
                "stock_concentration_g_L": stock_concentration,
                "stock_volume_ml": stock_volume_ml,
                "recommended": bool(mols_to_add[index] > ZERO_TOLERANCE),
            }
        )

    return {
        "best_combination": [FERTILIZER_NAMES[index] for index in best_indices],
        "reward": int(selected["reward"]),
        "maximum_reward": MAXIMUM_REWARD,
        "weighted_error": float(selected["weighted_error"]),
        "reservoir_volume_L": float(reservoir_volume_l),
        "nutrients": nutrient_results,
        "fertilizers": fertilizer_results,
        "warnings": _build_warnings(
            current_array,
            target_array,
            final_concentration,
            stock_concentrations,
        ),
    }
