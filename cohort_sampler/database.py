from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

import pandas as pd


@dataclass
class Database:
    engine: str
    config: dict[str, Any]

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "Database":
        prefix = config.get("env_prefix", "ANALYTICS_DB").upper()
        engine = os.getenv(f"{prefix}_ENGINE", config.get("engine", "clickhouse")).lower()
        values = {
            "host": os.getenv(f"{prefix}_HOST", "localhost"),
            "port": int(os.getenv(f"{prefix}_PORT", "8123" if engine == "clickhouse" else "5432")),
            "database": os.getenv(f"{prefix}_NAME", "default"),
            "user": os.getenv(f"{prefix}_USER", "default"),
            "password": os.getenv(f"{prefix}_PASSWORD", ""),
            "secure": os.getenv(f"{prefix}_SECURE", "false").lower() in {"1", "true", "yes"},
        }
        if engine not in {"clickhouse", "postgres"}:
            raise ValueError(f"Unsupported database engine: {engine}")
        return cls(engine, values)

    def query(self, sql: str, params: dict[str, Any] | None = None) -> pd.DataFrame:
        params = params or {}
        if self.engine == "clickhouse":
            import clickhouse_connect
            client = clickhouse_connect.get_client(
                host=self.config["host"], port=self.config["port"],
                username=self.config["user"], password=self.config["password"],
                database=self.config["database"], secure=self.config["secure"],
            )
            try:
                return client.query_df(sql, parameters=params)
            finally:
                client.close()
        import psycopg
        with psycopg.connect(
            host=self.config["host"], port=self.config["port"], dbname=self.config["database"],
            user=self.config["user"], password=self.config["password"], sslmode="require" if self.config["secure"] else "prefer",
        ) as connection:
            return pd.read_sql_query(sql, connection, params=params)

    def placeholder(self, name: str, value: Any, params: dict[str, Any]) -> str:
        params[name] = value
        if self.engine == "clickhouse":
            if isinstance(value, bool):
                kind = "UInt8"
            elif isinstance(value, int):
                kind = "Int64"
            elif isinstance(value, float):
                kind = "Float64"
            else:
                kind = "String"
            return "{" + name + ":" + kind + "}"
        return f"%({name})s"

    @property
    def random_function(self) -> str:
        return "rand()" if self.engine == "clickhouse" else "random()"
