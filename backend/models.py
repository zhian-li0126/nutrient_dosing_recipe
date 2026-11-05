"""Strict input and output schemas; JSON numeric values must be finite."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


FiniteNumber = Annotated[float, Field(strict=True, allow_inf_nan=False)]
NonnegativeNumber = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
PositiveNumber = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
ConcentrationVector = Annotated[list[NonnegativeNumber], Field(min_length=6, max_length=6)]
StockVector = Annotated[list[PositiveNumber | None], Field(min_length=6, max_length=6)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class CalculationRequest(StrictModel):
    target: ConcentrationVector
    current: ConcentrationVector
    reservoir_volume: PositiveNumber
    stock_concentrations: StockVector


class IonResult(StrictModel):
    id: str
    label: str
    formula: str
    target: NonnegativeNumber
    current: NonnegativeNumber
    added: NonnegativeNumber
    final: NonnegativeNumber
    error: FiniteNumber
    relative_error_percent: FiniteNumber | None


class FertilizerResult(StrictModel):
    id: str
    name: str
    formula: str
    grams: NonnegativeNumber
    stock_concentration: PositiveNumber | None
    stock_volume_ml: NonnegativeNumber | None


class CalculationMetrics(StrictModel):
    rmse_mg_l: NonnegativeNumber
    max_abs_error_mg_l: NonnegativeNumber
    total_fertilizer_g: NonnegativeNumber
    weighted_rmse: NonnegativeNumber


class CalculationResponse(StrictModel):
    ions: Annotated[list[IonResult], Field(min_length=6, max_length=6)]
    fertilizers: Annotated[list[FertilizerResult], Field(min_length=6, max_length=6)]
    metrics: CalculationMetrics
    warnings: list[str]
    assumptions: list[str]
