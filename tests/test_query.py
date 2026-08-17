from datetime import date

from cohort_sampler.config import Cohort, DateFilter, Filter, Metric
from cohort_sampler.database import Database
from cohort_sampler.query import build_query


def test_build_postgres_query_uses_parameters():
    cohort = Cohort("people", "People", "", "db", "SELECT * FROM people", ["person_id"], DateFilter("Date", "created_date"), [Filter("region", "Region", "region")], [Metric("events", "Events", "events")], [], ["all"])
    db = Database("postgres", {})
    sql, params = build_query(cohort, db, {"region": ["north' OR 1=1 --"]}, {"events": (1, 10)}, (date(2026, 1, 1), date(2026, 1, 31)), 50)
    assert "north' OR" not in sql
    assert params["filter_region_0"] == "north' OR 1=1 --"
    assert "LIMIT %(sample_limit)s" in sql
