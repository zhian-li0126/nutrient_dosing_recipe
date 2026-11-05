"""Ion and fertilizer definitions for pure, anhydrous salts.

The input basis is mg/L of each complete ionic species, not mg/L of N, S, or P.
These definitions are a transparent reconstruction from the supplied project
description. Commercial hydrated or blended fertilizers require their own
composition definitions before these recommendations can be used with them.
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Ion:
    id: str
    label: str
    formula: str
    molar_mass: float


@dataclass(frozen=True)
class Fertilizer:
    id: str
    name: str
    formula: str
    # Moles of each ion per mole of the fertilizer, in IONS order.
    ion_counts: tuple[int, ...]

    @property
    def molar_mass(self) -> float:
        return sum(count * ion.molar_mass for count, ion in zip(self.ion_counts, IONS))


# Conventional atomic masses in g/mol; the same values define each ion and salt.
H, N, O, K, CA, MG, S, P = 1.008, 14.007, 15.999, 39.0983, 40.078, 24.305, 32.06, 30.973761998

IONS = (
    Ion("nitrate", "Nitrate", "NO₃⁻", N + 3 * O),
    Ion("potassium", "Potassium", "K⁺", K),
    Ion("calcium", "Calcium", "Ca²⁺", CA),
    Ion("magnesium", "Magnesium", "Mg²⁺", MG),
    Ion("sulfate", "Sulfate", "SO₄²⁻", S + 4 * O),
    Ion("dihydrogen_phosphate", "Dihydrogen phosphate", "H₂PO₄⁻", 2 * H + P + 4 * O),
)

FERTILIZERS = (
    Fertilizer("calcium_nitrate", "Calcium nitrate", "Ca(NO₃)₂", (2, 0, 1, 0, 0, 0)),
    Fertilizer("potassium_nitrate", "Potassium nitrate", "KNO₃", (1, 1, 0, 0, 0, 0)),
    Fertilizer("potassium_sulfate", "Potassium sulfate", "K₂SO₄", (0, 2, 0, 0, 1, 0)),
    Fertilizer("magnesium_nitrate", "Magnesium nitrate", "Mg(NO₃)₂", (2, 0, 0, 1, 0, 0)),
    Fertilizer("magnesium_sulfate", "Magnesium sulfate", "MgSO₄", (0, 0, 0, 1, 1, 0)),
    Fertilizer("monopotassium_phosphate", "Monopotassium phosphate", "KH₂PO₄", (0, 1, 0, 0, 0, 1)),
)

DEFAULT_TARGET = (434.0, 117.3, 80.2, 24.6, 96.0, 50.0)
DEFAULT_CURRENT = (380.0, 100.0, 70.0, 20.0, 80.0, 40.0)
ASSUMPTIONS = (
    "All concentrations are mg/L of the listed ionic species, not elemental N, S, or P.",
    "Fertilizers are pure anhydrous salts and fully dissociate; hydrated or blended products need different composition data.",
    "The calculator recommends additions only; it does not remove nutrients or model dilution, uptake, pH, precipitation, or solubility.",
    "Reservoir volume is held constant; the volume of added stock solution is not included in predicted concentrations.",
    "Stock strengths are grams of the specified anhydrous fertilizer per liter of stock solution.",
    "The solution minimizes equally weighted relative ion errors, scaled by max(target, 1 mg/L); coupled ions may prevent an exact match.",
)


def mass_fraction_matrix() -> np.ndarray:
    """Return grams of each ion per gram of each fertilizer (6 by 6)."""
    return np.array(
        [
            [fertilizer.ion_counts[row] * ion.molar_mass / fertilizer.molar_mass
             for fertilizer in FERTILIZERS]
            for row, ion in enumerate(IONS)
        ],
        dtype=float,
    )


def public_configuration() -> dict:
    """Return UI metadata without serving optimizer code or the composition matrix."""
    return {
        "version": "1.0.0",
        "ions": [
            {"id": ion.id, "label": ion.label, "formula": ion.formula,
             "unit": "mg/L", "default_target": DEFAULT_TARGET[index]}
            for index, ion in enumerate(IONS)
        ],
        "fertilizers": [
            {"id": fertilizer.id, "name": fertilizer.name, "formula": fertilizer.formula,
             "default_stock_concentration": 100.0, "basis": "anhydrous"}
            for fertilizer in FERTILIZERS
        ],
        "defaults": {
            "target": list(DEFAULT_TARGET),
            "current": list(DEFAULT_CURRENT),
            "reservoir_volume": 80.0,
            "stock_concentrations": [100.0] * 6,
        },
        "assumptions": list(ASSUMPTIONS),
    }
