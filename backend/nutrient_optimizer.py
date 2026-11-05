"""Nonnegative nutrient additions using a weighted least-squares objective.

Let F contain ion mass fractions and z be fertilizer additions in g/L. The
optimizer minimizes ||(1000 F z - (target - current)) / max(target, 1)||²,
subject to z >= 0. Fertilizer masses are subsequently z * reservoir_volume.
Working in g/L keeps the optimization independent of reservoir size.

The signed residual deliberately preserves an existing excess: clamping a
negative deficit to zero would under-penalize fertilizers adding more of an ion
that is already above its target. The salt columns are not independent, so an
optimal mixture need not be unique; the predicted final ion vector is the
quantity to compare when validating equivalent formulations.
"""

import math

import numpy as np
from scipy.optimize import nnls

from .fertilizer_config import ASSUMPTIONS, FERTILIZERS, IONS, mass_fraction_matrix
from .models import CalculationRequest, CalculationResponse


def _stable_rmse(values: np.ndarray) -> float:
    """RMS without first squaring potentially large floating-point values."""
    largest = float(np.max(np.abs(values)))
    if largest == 0:
        return 0.0
    return largest * math.sqrt(float(np.mean(np.square(values / largest))))


def calculate_nutrients(request: CalculationRequest) -> CalculationResponse:
    """Calculate a nonnegative blend for a validated request.

    Raises ValueError if a finite but extreme input cannot be represented by
    the numerical solver or the returned units. No partially valid result is
    returned in that situation.
    """
    target = np.asarray(request.target, dtype=float)
    current = np.asarray(request.current, dtype=float)
    scale = np.maximum(target, 1.0)
    matrix = mass_fraction_matrix() * 1000.0

    try:
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            delta = target - current
            if np.all(delta <= 0):
                dose_g_per_l = np.zeros(6, dtype=float)
            else:
                dose_g_per_l, _ = nnls(matrix / scale[:, None], delta / scale, maxiter=1000)
            if not np.all(np.isfinite(dose_g_per_l)) or np.any(dose_g_per_l < 0):
                raise ValueError("The optimizer returned an invalid dose.")
            # Do not round the recommendation before calculating mass balance.
            added = matrix @ dose_g_per_l
            final = current + added
            error = final - target
            grams = dose_g_per_l * request.reservoir_volume
            stock_ml = [
                None if strength is None else float(grams[index] / strength * 1000.0)
                for index, strength in enumerate(request.stock_concentrations)
            ]
            percent_error = [
                None if target[index] == 0 else float(error[index] / target[index] * 100.0)
                for index in range(6)
            ]
            weighted_rmse = _stable_rmse(error / scale)
            total_grams = float(np.sum(grams))
    except (FloatingPointError, OverflowError, RuntimeError, ValueError) as exc:
        raise ValueError(
            "These values are outside the supported numerical range. "
            "Use realistic concentrations, reservoir volume, and stock strengths."
        ) from exc

    finite_outputs = [*added, *final, *error, *grams, weighted_rmse, total_grams]
    finite_outputs.extend(value for value in stock_ml if value is not None)
    finite_outputs.extend(value for value in percent_error if value is not None)
    if not all(math.isfinite(float(value)) for value in finite_outputs):
        raise ValueError("These inputs produce values outside the supported numerical range.")

    warnings = []
    tolerance = np.maximum(1e-6, 0.001 * scale)
    already_high = [ion.label for index, ion in enumerate(IONS)
                    if current[index] > target[index] + tolerance[index]]
    if already_high:
        warnings.append(
            "Already above target: " + ", ".join(already_high)
            + ". Additions cannot remove this excess."
        )
    if np.any(np.abs(error) > tolerance):
        warnings.append(
            "The targets cannot all be matched with the selected six salts and additions-only "
            "model. This result is a least-squares compromise; review the final concentrations."
        )
    overshoot = [ion.label for index, ion in enumerate(IONS)
                 if error[index] > tolerance[index] and added[index] > tolerance[index]]
    if overshoot:
        warnings.append(
            "Coupled fertilizer ions increase concentrations above target for: "
            + ", ".join(overshoot) + "."
        )
    if total_grams == 0:
        warnings.append("The best additions-only solution adds no fertilizer.")
    if any(strength is None and grams[index] > 0
           for index, strength in enumerate(request.stock_concentrations)):
        warnings.append("Some stock strengths are blank; those doses are reported in grams only.")
    known_stock_ml = sum(value for value in stock_ml if value is not None)
    if known_stock_ml > request.reservoir_volume * 1000.0 * 0.01:
        warnings.append(
            "The entered stock strengths require stock volume greater than one percent of the "
            "reservoir volume. The fixed-volume approximation may be unsuitable."
        )

    return CalculationResponse(
        ions=[
            {"id": ion.id, "label": ion.label, "formula": ion.formula,
             "target": float(target[index]), "current": float(current[index]),
             "added": float(added[index]), "final": float(final[index]),
             "error": float(error[index]), "relative_error_percent": percent_error[index]}
            for index, ion in enumerate(IONS)
        ],
        fertilizers=[
            {"id": fertilizer.id, "name": fertilizer.name, "formula": fertilizer.formula,
             "grams": float(grams[index]), "stock_concentration": request.stock_concentrations[index],
             "stock_volume_ml": stock_ml[index]}
            for index, fertilizer in enumerate(FERTILIZERS)
        ],
        metrics={"rmse_mg_l": _stable_rmse(error),
                 "max_abs_error_mg_l": float(np.max(np.abs(error))),
                 "total_fertilizer_g": total_grams, "weighted_rmse": weighted_rmse},
        warnings=warnings,
        assumptions=list(ASSUMPTIONS),
    )
