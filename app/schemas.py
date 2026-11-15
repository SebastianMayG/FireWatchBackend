"""Modelos de respuesta: aparecen documentados en /docs (OpenAPI) para el equipo de frontend."""
from typing import Any

from pydantic import BaseModel, Field


class MonthActivity(BaseModel):
    month: int = Field(description="1 = enero … 12 = diciembre")
    activity: float


class Indicators(BaseModel):
    year: int
    detections: int = Field(description="Detecciones crudas (todos los sensores) en el área y año")
    activity: float = Field(description="Actividad armonizada: Σ celdas-día ponderadas (comparable entre años)")
    peak_year: int | None = Field(description="Año completo con mayor actividad en el área")
    top_months: list[MonthActivity] = Field(description="Hasta 3 meses con mayor actividad en el año")
    median_activity: float = Field(description="Mediana de actividad de los años completos")
    vs_median_pct: float | None = Field(description="% de diferencia del año vs. la mediana histórica")
    years_analyzed: int
    estimated: bool = Field(description="True si el año depende de la calibración (solo MODIS, ≤2011)")
    partial: bool = Field(description="True si el año está incompleto (2000)")


class CompareDelta(BaseModel):
    activity_pct: float | None = Field(description="% de cambio de b respecto de a")
    detections_pct: float | None
    activity_abs: float
    detections_abs: int


class CompareBasis(BaseModel):
    """Comparación justa entre los dos años: usa una métrica que ambos midieron igual."""

    metric: str = Field(description="Métrica usada para comparar: siempre `activity` (actividad armonizada)")
    a: float = Field(description="Valor de year_a en esa métrica")
    b: float = Field(description="Valor de year_b en esa métrica")
    pct_b_vs_a: float | None
    pct_a_vs_b: float | None
    peak_years: list[int] = Field(description="Año con más actividad de los dos (ambos si empatan)")
    low_data: bool = Field(description="True si alguno de los años tiene pocas detecciones: comparación poco confiable")
    low_data_threshold: int


class Compare(BaseModel):
    a: Indicators
    b: Indicators
    basis: CompareBasis
    delta: CompareDelta


class Calendar(BaseModel):
    years: list[int] = Field(description="Filas de la matriz")
    months: list[int] = Field(description="Columnas de la matriz (1-12)")
    values: list[list[float]] = Field(description="values[i][j] = actividad del año years[i], mes months[j]")
    max: float = Field(description="Valor máximo, para la escala de color")
    estimated_years: list[int]
    partial_years: list[int]


class TrendPoint(BaseModel):
    year: int
    activity: float
    detections: int
    estimated: bool
    partial: bool


class Trend(BaseModel):
    series: list[TrendPoint]
    median_activity: float
    peak_year: int | None


class Report(BaseModel):
    bbox: list[float]
    year: int
    indicators: Indicators
    trend: Trend
    calendar: Calendar
    methodology: str
    attribution: str


class Meta(BaseModel):
    years: list[int]
    default_year: int
    complete_years: list[int]
    estimated_years: list[int]
    partial_years: list[int]
    sensors: list[str]
    default_bbox: list[float]
    grid_deg: float
    points_limit: int
    recurrent_zones: dict[str, Any]
    calibration: dict[str, Any]
    quality_report: dict[str, Any]
    attribution: str
