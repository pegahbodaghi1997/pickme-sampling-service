from __future__ import annotations

from datetime import date
from typing import Any

from .config import Cohort
from .database import Database


def build_query(
    cohort: Cohort,
    db: Database,
    selected_filters: dict[str, list[Any]],
    metric_ranges: dict[str, tuple[float, float]],
    date_range: tuple[date, date] | None,
    limit: int | None = None,
    count_only: bool = False,
) -> tuple[str, dict[str, Any]]:
    params: dict[str, Any] = {}
    clauses: list[str] = []
    if cohort.date_filter and date_range:
        start, end = date_range
        p1 = db.placeholder("date_start", start.isoformat(), params)
        p2 = db.placeholder("date_end", end.isoformat(), params)
        clauses.append(f"source.{cohort.date_filter.column} BETWEEN {p1} AND {p2}")
    for item in cohort.filters:
        values = selected_filters.get(item.key) or []
        if values:
            placeholders = [db.placeholder(f"filter_{item.key}_{i}", value, params) for i, value in enumerate(values)]
            clauses.append(f"source.{item.column} IN ({', '.join(placeholders)})")
    for metric in cohort.metrics:
        if metric.key in metric_ranges:
            low, high = metric_ranges[metric.key]
            p1 = db.placeholder(f"metric_{metric.key}_min", low, params)
            p2 = db.placeholder(f"metric_{metric.key}_max", high, params)
            clauses.append(f"source.{metric.column} BETWEEN {p1} AND {p2}")
    where = " AND ".join(clauses) if clauses else "1 = 1"
    wrapped = f"FROM ({cohort.base_query}) AS source WHERE {where}"
    if count_only:
        return f"SELECT count(*) AS matching_rows {wrapped}", params
    columns = list(dict.fromkeys(cohort.id_columns + [f.column for f in cohort.filters] + [m.column for m in cohort.metrics] + [s.column for s in cohort.stratify_columns]))
    limit_sql = ""
    if limit is not None:
        p = db.placeholder("sample_limit", int(limit), params)
        limit_sql = f" LIMIT {p}"
    return f"SELECT {', '.join('source.' + c for c in columns)} {wrapped} ORDER BY {db.random_function}{limit_sql}", params
