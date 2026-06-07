from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from app.config import load_weights
from app.models import Confidence, MatchData, RatingBreakdown, StatisticValue, TeamPayload
from app.stat_catalog import VariableSpec, group_labels, iter_variable_specs


RATING_GROUPS = {
    "offensive": ["attack", "general_strength", "home_away"],
    "defensive": ["defense", "general_strength", "home_away"],
    "midfield": ["midfield_control"],
    "goalkeeper": ["goalkeeper"],
    "squad": ["squad", "injuries_suspensions"],
    "recent_form": ["recent_form", "fatigue_schedule"],
}


@dataclass(frozen=True)
class PreparedStats:
    frame: pd.DataFrame
    ratings: dict[str, RatingBreakdown]
    influence_percentages: dict[str, float]


class StatisticalEngine:
    """Convert validated stats into weighted ratings without hard-coding variables.

    The engine reads variable definitions and weights from config files. New
    variables can be added to the catalog and, optionally, to weights.json; the
    normalization loop will consume them automatically. The default weighting is
    a transparent expert-prior layer designed to be replaceable by ML feature
    importances in the future.
    """

    def __init__(self) -> None:
        self.weights = load_weights()
        self.confidence_multipliers: dict[str, float] = self.weights["confidence_multipliers"]
        self.group_weights: dict[str, float] = self.weights["group_weights"]
        self.priority_weights: dict[str, float] = self.weights["priority_variable_weights"]

    def prepare(self, match: MatchData) -> PreparedStats:
        rows = []
        for side, team in (("local", match.local), ("visitante", match.visitante)):
            rows.extend(self._team_rows(side, team))
        frame = pd.DataFrame(rows)
        frame["normalized"] = self._normalize_frame(frame)
        frame["effective_weight"] = frame["group_weight"] * frame["variable_weight"] * frame["confidence_weight"]
        ratings = {
            "local": self._build_ratings(frame[frame["side"] == "local"]),
            "visitante": self._build_ratings(frame[frame["side"] == "visitante"]),
        }
        influence = self._influence_percentages(frame)
        return PreparedStats(frame=frame, ratings=ratings, influence_percentages=influence)

    def _team_rows(self, side: str, team: TeamPayload) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for spec in iter_variable_specs():
            stat = team.estadisticas[spec.group][spec.key]
            numeric = _as_float(stat.valor)
            full_key = spec.full_key
            rows.append(
                {
                    "side": side,
                    "group": spec.group,
                    "key": spec.key,
                    "full_key": full_key,
                    "name": spec.name,
                    "direction": spec.direction,
                    "value": numeric,
                    "raw_value": stat.valor,
                    "source": stat.fuente,
                    "confidence": stat.confianza.value if isinstance(stat.confianza, Confidence) else str(stat.confianza),
                    "confidence_weight": self.confidence_multipliers.get(stat.confianza.value if isinstance(stat.confianza, Confidence) else str(stat.confianza), 0.35),
                    "group_weight": self.group_weights.get(spec.group, 1.0),
                    "variable_weight": self.priority_weights.get(full_key, 1.0),
                }
            )
        return rows

    def _normalize_frame(self, frame: pd.DataFrame) -> pd.Series:
        normalized = pd.Series(np.nan, index=frame.index, dtype=float)
        for full_key, subset in frame.groupby("full_key"):
            values = subset["value"].astype(float)
            available = values.dropna()
            if available.empty:
                normalized.loc[subset.index] = 0.5
                continue
            if len(available) == 1 or math.isclose(float(available.max()), float(available.min())):
                normalized.loc[subset.index] = values.apply(lambda value: 0.55 if not pd.isna(value) else 0.5)
                continue
            min_value, max_value = float(available.min()), float(available.max())
            scaled = (values - min_value) / (max_value - min_value)
            direction = str(subset["direction"].iloc[0])
            if direction == "lower":
                scaled = 1 - scaled
            elif direction == "neutral":
                midpoint = (min_value + max_value) / 2
                half_range = max((max_value - min_value) / 2, 1e-9)
                scaled = 1 - ((values - midpoint).abs() / half_range).clip(0, 1)
            normalized.loc[subset.index] = scaled.fillna(0.5)
        return normalized.clip(0, 1)

    def _build_ratings(self, team_frame: pd.DataFrame) -> RatingBreakdown:
        group_scores = {
            group: _weighted_mean(group_frame["normalized"], group_frame["effective_weight"])
            for group, group_frame in team_frame.groupby("group")
        }

        def rating_for(groups: Iterable[str]) -> float:
            selected = team_frame[team_frame["group"].isin(groups)]
            return round(_weighted_mean(selected["normalized"], selected["effective_weight"]) * 100, 2)

        global_score = _weighted_mean(team_frame["normalized"], team_frame["effective_weight"]) * 100
        return RatingBreakdown(
            offensive=rating_for(RATING_GROUPS["offensive"]),
            defensive=rating_for(RATING_GROUPS["defensive"]),
            midfield=rating_for(RATING_GROUPS["midfield"]),
            goalkeeper=rating_for(RATING_GROUPS["goalkeeper"]),
            squad=rating_for(RATING_GROUPS["squad"]),
            recent_form=rating_for(RATING_GROUPS["recent_form"]),
            global_score=round(global_score, 2),
            group_scores={group: round(score * 100, 2) for group, score in group_scores.items()},
        )

    def _influence_percentages(self, frame: pd.DataFrame) -> dict[str, float]:
        labels = group_labels()
        totals = frame.groupby("group")["effective_weight"].sum().to_dict()
        total = sum(totals.values()) or 1.0
        return {labels.get(group, group): round(weight / total * 100, 2) for group, weight in totals.items()}


def _as_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("€", "").replace("%", "").replace(",", ".").strip()
        multiplier = 1.0
        lower = cleaned.lower()
        if lower.endswith("m"):
            multiplier = 1_000_000.0
            cleaned = cleaned[:-1]
        elif lower.endswith("k"):
            multiplier = 1_000.0
            cleaned = cleaned[:-1]
        try:
            return float(cleaned) * multiplier
        except ValueError:
            return None
    return None


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & weights.notna() & (weights > 0)
    if not valid.any():
        return 0.5
    return float(np.average(values[valid].astype(float), weights=weights[valid].astype(float)))
