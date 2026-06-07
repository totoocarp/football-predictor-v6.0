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
            "elo_global_local_menos_visitante": _json_number(elo_diff),
            "xg_difference_local_menos_visitante": _json_number(xg_diff),
            "xg_local_en_casa": _json_number(home_xg),
            "xg_visitante_fuera": _json_number(away_xg),
        },
        "impacto_localia": "La localía aumenta el lambda del equipo local mediante el multiplicador configurable de simulación y las variables específicas home_away.",
        "fortalezas_debilidades": _build_strengths_and_weaknesses(match, prepared),
        "lectura_probabilidades": f"{match.local.nombre}: {simulation.home_win_probability}%, empate: {simulation.draw_probability}%, {match.visitante.nombre}: {simulation.away_win_probability}%.",
    }


def _build_strengths_and_weaknesses(match: MatchData, prepared: PreparedStats) -> dict[str, dict[str, list[str]]]:
    """Generate qualitative notes in Python so Gemini only supplies raw data."""
    local_scores = prepared.ratings["local"].group_scores
    visitor_scores = prepared.ratings["visitante"].group_scores
    return {
        match.local.nombre: _team_notes(local_scores, visitor_scores),
        match.visitante.nombre: _team_notes(visitor_scores, local_scores),
    }


def _team_notes(own_scores: dict[str, float], rival_scores: dict[str, float]) -> dict[str, list[str]]:
    deltas = []
    for group, own_value in own_scores.items():
        rival_value = rival_scores.get(group)
        if rival_value is None:
            continue
        deltas.append((group, own_value - rival_value))
    strengths = [f"Ventaja en {group.replace('_', ' ')} ({delta:+.1f})" for group, delta in sorted(deltas, key=lambda item: item[1], reverse=True)[:3] if delta > 2]
    weaknesses = [f"Desventaja en {group.replace('_', ' ')} ({delta:+.1f})" for group, delta in sorted(deltas, key=lambda item: item[1])[:3] if delta < -2]
    return {"fortalezas": strengths, "debilidades": weaknesses}


def _append_edge(home: list[str], away: list[str], label: str, home_value: float, away_value: float, home_name: str, away_name: str) -> None:
    if not (_is_finite(home_value) and _is_finite(away_value)):
        return
    diff = home_value - away_value
    if abs(diff) < 3:
        return
    text = f"{label}: ventaja de {abs(diff):.1f} puntos para "
    if diff > 0:
        home.append(text + home_name)
    else:
        away.append(text + away_name)


def _safe_difference(left_frame: pd.DataFrame, right_frame: pd.DataFrame, key: str) -> float | None:
    left = _value(left_frame, key)
    right = _value(right_frame, key)
    if not (_is_finite(left) and _is_finite(right)):
        return None
    return left - right


def _value(frame: pd.DataFrame, key: str) -> float:
    try:
        value = frame.loc[key, "value"]
    except KeyError:
        return float("nan")
    if pd.isna(value):
        return float("nan")
    return float(value)


def _json_number(value: float | None) -> float | None:
    if value is None or not _is_finite(value):
        return None
    return round(float(value), 2)


def _is_finite(value: float | None) -> bool:
    return value is not None and math.isfinite(float(value))


def _injury_summary(frame: pd.DataFrame) -> dict[str, float | None]:
    keys = {
        "titulares_lesionados": "injuries_suspensions.injured_starters",
        "titulares_suspendidos": "injuries_suspensions.suspended_starters",
        "valor_mercado_lesionado": "injuries_suspensions.injured_market_value",
        "minutos_perdidos": "injuries_suspensions.minutes_lost_absences",
    }
    summary: dict[str, float | None] = {}
    for label, key in keys.items():
        summary[label] = _json_number(_value(frame, key))
    return summary
