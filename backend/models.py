"""Validated API request models."""

from __future__ import annotations

import math
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


MAX_CONCENTRATION_MG_L = 1_000_000.0
MAX_RESERVOIR_VOLUME_L = 100_000_000.0
MAX_STOCK_CONCENTRATION_G_L = 1_000_000.0

ConcentrationVector = Annotated[list[float], Field(min_length=6, max_length=6)]
StockVector = Annotated[list[float | None], Field(min_length=6, max_length=6)]


class CalculateRequest(BaseModel):
    """Request body for a nutrient addition calculation."""

    model_config = ConfigDict(extra="forbid")

    target: ConcentrationVector
    current: ConcentrationVector
    reservoir_volume: float = Field(
        gt=0,
        le=MAX_RESERVOIR_VOLUME_L,
        description="Reservoir volume in liters.",
    )
    stock_concentrations: StockVector = Field(
        description="Optional stock strengths in grams of fertilizer per liter.",
    )

    @field_validator("target", "current")
    @classmethod
    def validate_concentrations(cls, values: list[float]) -> list[float]:
        for value in values:
            if not math.isfinite(value):
                raise ValueError("concentrations must be finite numbers")
            if value < 0:
                raise ValueError("concentrations cannot be negative")
            if value > MAX_CONCENTRATION_MG_L:
                raise ValueError(
                    f"concentrations cannot exceed {MAX_CONCENTRATION_MG_L:g} mg/L"
                )
        return values

    @field_validator("reservoir_volume")
    @classmethod
    def validate_reservoir_volume(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("reservoir volume must be a finite number")
        return value

    @field_validator("stock_concentrations")
    @classmethod
    def validate_stock_concentrations(
        cls, values: list[float | None]
    ) -> list[float | None]:
        for value in values:
            if value is None:
                continue
            if not math.isfinite(value):
                raise ValueError("stock concentrations must be finite numbers")
            if value <= 0:
                raise ValueError(
                    "stock concentrations must be positive when provided"
                )
            if value > MAX_STOCK_CONCENTRATION_G_L:
                raise ValueError(
                    "stock concentrations cannot exceed "
                    f"{MAX_STOCK_CONCENTRATION_G_L:g} g/L"
                )
        return values

