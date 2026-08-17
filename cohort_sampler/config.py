from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import re

import yaml

IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class DateFilter:
    label: str
    column: str


@dataclass(frozen=True)
class Filter:
    key: str
    label: str
    column: str
    values: list[Any] = field(default_factory=list)
    values_query: str | None = None


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    column: str
    default_min: float = 0
    default_max: float | None = None
    step: float = 1


@dataclass(frozen=True)
class Stratifier:
    label: str
    column: str


@dataclass(frozen=True)
class Cohort:
    key: str
    title: str
    description: str
    database: str
    base_query: str
    id_columns: list[str]
    date_filter: DateFilter | None
    filters: list[Filter]
    metrics: list[Metric]
    stratify_columns: list[Stratifier]
    allowed_roles: list[str]


@dataclass(frozen=True)
class Settings:
    app: dict[str, Any]
    databases: dict[str, dict[str, Any]]
    cohorts: list[Cohort]


def _identifier(value: str) -> str:
    if not IDENTIFIER.fullmatch(value):
        raise ValueError(f"Invalid column identifier: {value!r}")
    return value


def _read_only_query(query: str) -> str:
    clean = query.strip().rstrip(";").strip()
    if not re.match(r"^(SELECT|WITH)\b", clean, re.IGNORECASE):
        raise ValueError("base_query and values_query must start with SELECT or WITH")
    if ";" in clean:
        raise ValueError("Only one SQL statement is allowed")
    return clean


def load_settings(path: str | Path) -> Settings:
    with Path(path).open(encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    databases = raw.get("databases") or {}
    if not databases:
        raise ValueError("At least one database must be configured")
    cohorts: list[Cohort] = []
    seen: set[str] = set()
    for item in raw.get("cohorts") or []:
        key = _identifier(item["key"])
        if key in seen:
            raise ValueError(f"Duplicate cohort key: {key}")
        seen.add(key)
        database = item["database"]
        if database not in databases:
            raise ValueError(f"Unknown database {database!r} in cohort {key!r}")
        date_raw = item.get("date_filter")
        date_filter = DateFilter(date_raw["label"], _identifier(date_raw["column"])) if date_raw else None
        filters = [Filter(
            key=_identifier(f["key"]), label=f["label"], column=_identifier(f["column"]),
            values=f.get("values") or [],
            values_query=_read_only_query(f["values_query"]) if f.get("values_query") else None,
        ) for f in item.get("filters", [])]
        metrics = [Metric(
            key=_identifier(m["key"]), label=m["label"], column=_identifier(m["column"]),
            default_min=m.get("default_min", 0), default_max=m.get("default_max"), step=m.get("step", 1),
        ) for m in item.get("metrics", [])]
        stratifiers = [Stratifier(s["label"], _identifier(s["column"])) for s in item.get("stratify_columns", [])]
        ids = [_identifier(x) for x in item["id_columns"]]
        cohorts.append(Cohort(
            key=key, title=item["title"], description=item.get("description", ""),
            database=database, base_query=_read_only_query(item["base_query"]), id_columns=ids,
            date_filter=date_filter, filters=filters, metrics=metrics,
            stratify_columns=stratifiers, allowed_roles=item.get("allowed_roles", ["all"]),
        ))
    if not cohorts:
        raise ValueError("At least one cohort must be configured")
    return Settings(app=raw.get("app") or {}, databases=databases, cohorts=cohorts)
