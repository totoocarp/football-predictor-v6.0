from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import poisson

from app.config import load_weights
from app.models import MatchData, RatingBreakdown, SimulationResult
from app.stat_engine import PreparedStats


class MonteCarloSimulator:
    def __init__(self) -> None:
        self.settings = load_weights()["simulation"]

    def run(self, match: MatchData, prepared: PreparedStats, simulations: int | None = None) -> SimulationResult:
        n = simulations or int(self.settings["default_simulations"])
        home_rating = prepared.ratings["local"]
        away_rating = prepared.ratings["visitante"]
        home_lambda = self._expected_goals("local", home_rating, away_rating, prepared)
        away_lambda = self._expected_goals("visitante", away_rating, home_rating, prepared)

        rng = np.random.default_rng()
        home_goals = poisson.rvs(mu=home_lambda, size=n, random_state=rng)
        away_goals = poisson.rvs(mu=away_lambda, size=n, random_state=rng)

        # A small shared-match-state correction keeps draw rates realistic without
        # replacing independent team Poisson lambdas. The value is configurable.
        corr = float(self.settings.get("draw_correlation", 0.0))
        if corr > 0:
            mask = rng.random(n) < corr
            shared = poisson.rvs(mu=max(min(home_lambda, away_lambda) * 0.35, 0.05), size=int(mask.sum()), random_state=rng)
            home_goals[mask] = shared
            away_goals[mask] = shared

        results = pd.DataFrame({"home": home_goals, "away": away_goals})
        home_wins = float((results["home"] > results["away"]).mean())
        draws = float((results["home"] == results["away"]).mean())
        away_wins = float((results["home"] < results["away"]).mean())
        score_counts = Counter(zip(results["home"].astype(int), results["away"].astype(int)))
        top_scores = [
            {"score": f"{home}-{away}", "count": count, "probability": round(count / n * 100, 2)}
            for (home, away), count in score_counts.most_common(10)
        ]
        return SimulationResult(
            home_win_probability=round(home_wins * 100, 2),
            draw_probability=round(draws * 100, 2),
            away_win_probability=round(away_wins * 100, 2),
            top_scores=top_scores,
            expected_goals={match.local.nombre: round(home_lambda, 3), match.visitante.nombre: round(away_lambda, 3)},
        )

    def _expected_goals(
        self,
        side: str,
        own: RatingBreakdown,
        rival: RatingBreakdown,
        prepared: PreparedStats,
    ) -> float:
        frame = prepared.frame[prepared.frame["side"] == side].set_index("full_key")
        rival_side = "visitante" if side == "local" else "local"
        rival_frame = prepared.frame[prepared.frame["side"] == rival_side].set_index("full_key")

        base_xg = _value(frame, "attack.xg", _value(frame, "general_strength.xg_per_match", 1.25))
        rival_xga = _value(rival_frame, "defense.xga", _value(rival_frame, "general_strength.goals_conceded_per_match", 1.25))
        historical_component = np.nanmean([base_xg, rival_xga])
        if np.isnan(historical_component):
            historical_component = 1.25

        rating_scale = float(self.settings["rating_scale"])
        attack_factor = 1 + ((own.offensive - 50) / 50) * rating_scale
        defense_factor = 1 - ((rival.defensive - 50) / 50) * rating_scale
        form_factor = 1 + ((own.recent_form - rival.recent_form) / 100) * float(self.settings["form_scale"])
        injury_factor = 1 - _absence_load(frame) * float(self.settings["injury_scale"])
        fatigue_factor = 1 + _fatigue_edge(frame, rival_frame) * float(self.settings["fatigue_scale"])
        market_factor = 1 + _market_edge(side, frame, rival_frame) * float(self.settings["market_blend"])
        home_factor = float(self.settings["home_advantage_goal_multiplier"]) if side == "local" else 0.96

        lam = historical_component * attack_factor * defense_factor * form_factor * injury_factor * fatigue_factor * market_factor * home_factor
        return float(np.clip(lam, float(self.settings["min_lambda"]), float(self.settings["max_lambda"])))


def _value(frame: pd.DataFrame, key: str, default: float | None = None) -> float:
    try:
        value = frame.loc[key, "value"]
    except KeyError:
        return float(default) if default is not None else float("nan")
    if pd.isna(value):
        return float(default) if default is not None else float("nan")
    return float(value)


def _absence_load(frame: pd.DataFrame) -> float:
    starters = _value(frame, "injuries_suspensions.injured_starters", 0) + _value(frame, "injuries_suspensions.suspended_starters", 0)
    injured_value = _value(frame, "injuries_suspensions.injured_market_value", 0)
    total_value = max(_value(frame, "squad.total_market_value", 1), 1)
    value_share = min(injured_value / total_value, 0.5)
    return float(np.clip(starters / 11 * 0.7 + value_share * 0.3, 0, 0.7))


def _fatigue_edge(frame: pd.DataFrame, rival_frame: pd.DataFrame) -> float:
    rest_edge = _value(frame, "fatigue_schedule.rest_days", 4) - _value(rival_frame, "fatigue_schedule.rest_days", 4)
    congestion_edge = _value(rival_frame, "fatigue_schedule.matches_last_14_days", 2) - _value(frame, "fatigue_schedule.matches_last_14_days", 2)
    return float(np.clip(rest_edge / 7 + congestion_edge / 4, -1, 1))


def _market_edge(side: str, frame: pd.DataFrame, rival_frame: pd.DataFrame) -> float:
    own_key = "betting_market.home_implied_probability" if side == "local" else "betting_market.away_implied_probability"
    rival_key = "betting_market.away_implied_probability" if side == "local" else "betting_market.home_implied_probability"
    own_prob = _value(frame, own_key, 33)
    rival_prob = _value(rival_frame, rival_key, 33)
    if own_prob > 1 or rival_prob > 1:
        own_prob /= 100
        rival_prob /= 100
    return float(np.clip(own_prob - rival_prob, -0.5, 0.5))
