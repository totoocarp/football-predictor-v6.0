from __future__ import annotations

from copy import deepcopy

from app.models import Confidence, MatchData, StatisticValue, TeamPayload
from app.stat_catalog import iter_variable_specs


def validate_and_complete_match(data: MatchData) -> MatchData:
    """Ensure every required variable exists; unverifiable values stay null/LOW.

    Gemini is instructed not to infer unavailable facts. The application mirrors
    that rule by filling absent variables with null values and LOW confidence so
    the statistical engine can ignore or down-weight them without changing its
    code when new variables are added to the catalog.
    """
    completed = deepcopy(data)
    completed.local = _complete_team(completed.local)
    completed.visitante = _complete_team(completed.visitante)
    return completed


def _complete_team(team: TeamPayload) -> TeamPayload:
    for spec in iter_variable_specs():
        team.estadisticas.setdefault(spec.group, {})
        team.estadisticas[spec.group].setdefault(
            spec.key,
            StatisticValue(valor=None, fuente="Dato no verificado por Gemini", confianza=Confidence.LOW),
        )
    return team
