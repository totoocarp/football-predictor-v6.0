from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class StatisticValue(BaseModel):
    valor: float | int | str | None = None
    fuente: str = Field(default="No verificada")
    confianza: Confidence = Confidence.LOW

    @field_validator("fuente")
    @classmethod
    def source_is_not_empty(cls, value: str) -> str:
        return value.strip() or "No verificada"


class TeamPayload(BaseModel):
    nombre: str
    estadisticas: dict[str, dict[str, StatisticValue]]
    fortalezas: list[str] = Field(default_factory=list)
    debilidades: list[str] = Field(default_factory=list)
    notas_fuentes: list[str] = Field(default_factory=list)


class MatchData(BaseModel):
    local: TeamPayload
    visitante: TeamPayload
    contexto: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_team_names(self) -> "MatchData":
        self.local.nombre = self.local.nombre.strip()
        self.visitante.nombre = self.visitante.nombre.strip()
        return self


class PredictionRequest(BaseModel):
    local: str = Field(min_length=2, max_length=80)
    visitante: str = Field(min_length=2, max_length=80)
    force_refresh: bool = False
    simulations: int = Field(default=20000, ge=1000, le=100000)

    @field_validator("local", "visitante")
    @classmethod
    def clean_team_name(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def teams_must_differ(self) -> "PredictionRequest":
        if self.local.lower() == self.visitante.lower():
            raise ValueError("Los equipos local y visitante deben ser diferentes.")
        return self


class RatingBreakdown(BaseModel):
    offensive: float
    defensive: float
    midfield: float
    goalkeeper: float
    squad: float
    recent_form: float
    global_score: float
    group_scores: dict[str, float]


class SimulationResult(BaseModel):
    home_win_probability: float
    draw_probability: float
    away_win_probability: float
    top_scores: list[dict[str, float | str | int]]
    expected_goals: dict[str, float]


class PredictionResponse(BaseModel):
    match: MatchData
    ratings: dict[str, RatingBreakdown]
    group_influence_percentages: dict[str, float]
    simulation: SimulationResult
    explanation: dict[str, Any]
    cached: bool
