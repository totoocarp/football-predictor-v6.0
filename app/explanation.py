from __future__ import annotations

import math
from typing import Any

import pandas as pd

from app.models import MatchData, SimulationResult
from app.stat_engine import PreparedStats


def build_explanation(match: MatchData, prepared: PreparedStats, simulation: SimulationResult) -> dict[str, Any]:
    local = prepared.ratings["local"]
    visitor = prepared.ratings["visitante"]
    local_frame = prepared.frame[prepared.frame["side"] == "local"].set_index("full_key")
    visitor_frame = prepared.frame[prepared.frame["side"] == "visitante"].set_index("full_key")

    factors_home: list[str] = []
    factors_away: list[str] = []
    _append_edge(factors_home, factors_away, "rating global", local.global_score, visitor.global_score, match.local.nombre, match.visitante.nombre)
    _append_edge(factors_home, factors_away, "rating ofensivo", local.offensive, visitor.offensive, match.local.nombre, match.visitante.nombre)
    _append_edge(factors_home, factors_away, "forma reciente", local.recent_form, visitor.recent_form, match.local.nombre, match.visitante.nombre)
    _append_edge(factors_home, factors_away, "defensa", local.defensive, visitor.defensive, match.local.nombre, match.visitante.nombre)

    elo_diff = _safe_difference(local_frame, visitor_frame, "general_strength.elo_global")
    xg_diff = _safe_difference(local_frame, visitor_frame, "general_strength.xg_difference")
    elo_diff = _value(local_frame, "general_strength.elo_global") - _value(visitor_frame, "general_strength.elo_global")
    xg_diff = _value(local_frame, "general_strength.xg_difference") - _value(visitor_frame, "general_strength.xg_difference")
    home_xg = _value(local_frame, "home_away.home_xg")
    away_xg = _value(visitor_frame, "home_away.away_xg")

    injuries = {
        match.local.nombre: _injury_summary(local_frame),
        match.visitante.nombre: _injury_summary(visitor_frame),
    }
    return {
        "factores_local": factors_home,
        "factores_visitante": factors_away,
        "lesiones_importantes": injuries,
        "diferencias_clave": {
            "elo_global_local_menos_visitante": round(elo_diff, 2),
            "xg_difference_local_menos_visitante": round(xg_diff, 2),
            "xg_local_en_casa": None if pd.isna(home_xg) else round(home_xg, 2),
            "xg_visitante_fuera": None if pd.isna(away_xg) else round(away_xg, 2),
        },
        "impacto_localia": "La localía aumenta el lambda del equipo local mediante el multiplicador configurable de simulación y las variables específicas home_away.",
        "fortalezas_debilidades": {
            match.local.nombre: {"fortalezas": match.local.fortalezas, "debilidades": match.local.debilidades},
            match.visitante.nombre: {"fortalezas": match.visitante.fortalezas, "debilidades": match.visitante.debilidades},
        },
        "lectura_probabilidades": f"{match.local.nombre}: {simulation.home_win_probability}%, empate: {simulation.draw_probability}%, {match.visitante.nombre}: {simulation.away_win_probability}%.",
    }


def _append_edge(home: list[str], away: list[str], label: str, home_value: float, away_value: float, home_name: str, away_name: str) -> None:
    diff = home_value - away_value
    if abs(diff) < 3:
        return
    text = f"{label}: ventaja de {abs(diff):.1f} puntos para "
    if diff > 0:
        home.append(text + home_name)
    else:
        away.append(text + away_name)


def _value(frame: pd.DataFrame, key: str) -> float:
    try:
        value = frame.loc[key, "value"]
    except KeyError:
        return float("nan")
    if pd.isna(value):
        return float("nan")
    return float(value)


def _injury_summary(frame: pd.DataFrame) -> dict[str, float | None]:
    keys = {
        "titulares_lesionados": "injuries_suspensions.injured_starters",
        "titulares_suspendidos": "injuries_suspensions.suspended_starters",
        "valor_mercado_lesionado": "injuries_suspensions.injured_market_value",
        "minutos_perdidos": "injuries_suspensions.minutes_lost_absences",
    }
    summary: dict[str, float | None] = {}
    for label, key in keys.items():
        value = _value(frame, key)
        summary[label] = None if pd.isna(value) else round(value, 2)
    return summary
