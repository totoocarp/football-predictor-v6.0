from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from app.config import load_variable_catalog


@dataclass(frozen=True)
class VariableSpec:
    group: str
    key: str
    name: str
    direction: str
    required: bool = True

    @property
    def full_key(self) -> str:
        return f"{self.group}.{self.key}"


def iter_variable_specs() -> Iterator[VariableSpec]:
    catalog = load_variable_catalog()
    for group in catalog["groups"]:
        for variable in group["variables"]:
            yield VariableSpec(
                group=group["key"],
                key=variable["key"],
                name=variable["name"],
                direction=variable.get("direction", "higher"),
                required=variable.get("required", True),
            )


def group_labels() -> dict[str, str]:
    return {group["key"]: group["label"] for group in load_variable_catalog()["groups"]}
