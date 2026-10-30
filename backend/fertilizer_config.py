"""Server-side fertilizer display names and anhydrous molecular weights."""

from __future__ import annotations

import numpy as np


FERTILIZER_NAMES: tuple[str, ...] = (
    "Ca(NO3)2",
    "KNO3",
    "K2SO4",
    "Mg(NO3)2",
    "MgSO4",
    "KH2PO4",
)

# g/mol for the anhydrous fertilizer formulas listed above.
COMPOUND_MOLAR_MASS = np.array(
    [164.0, 101.0, 174.0, 148.0, 120.0, 136.0],
    dtype=float,
)

