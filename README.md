# Cohort Sampler

A configuration-driven Streamlit service for selecting random cohorts and creating balanced experiment groups from data stored in ClickHouse or PostgreSQL.

The application contains no company-specific tables, metrics, filters, or terminology. Everything that describes your data lives in a YAML configuration file.

## Features

- Multiple independently configured cohorts
- ClickHouse and PostgreSQL support
- Dynamic or static categorical filters
- Date and numeric-range filters
- Random sampling with a preview count
- Control/treatment splitting with optional stratification
- Balance diagnostics (means, medians, standard deviations, Cohen's d, Mann–Whitney U, KS, and Welch t-test)
- Optional role-based login
- CSV downloads
- Docker support

## Quick start

1. Copy the environment template:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your database connection and configuration path.

3. Edit `configs/example.yaml`. Its base query must return every column referenced by `id_columns`, `date_filter`, `filters`, `metrics`, or `stratify_columns`.

4. Install and run:

   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   streamlit run app.py
   ```

Open <http://localhost:8501>.

## Configuration

Set `SAMPLER_CONFIG` to a YAML file. The included example is vendor-neutral:

```yaml
app:
  title: Cohort Sampler
  primary_color: "#4f46e5"

cohorts:
  - key: account_activity
    title: Account activity
    database: analytics
    base_query: |
      SELECT account_id, event_date, region, plan, events, conversions
      FROM analytics.account_activity
    id_columns: [account_id]
    date_filter:
      label: Activity date
      column: event_date
    filters:
      - key: region
        label: Region
        column: region
        values_query: SELECT DISTINCT region FROM analytics.account_activity ORDER BY region
    metrics:
      - key: events
        label: Event count
        column: events
        default_min: 0
    stratify_columns:
      - label: Plan
        column: plan
```

### Filter values

A categorical filter can use either:

- `values: [free, pro, enterprise]` for a static list, or
- `values_query: SELECT DISTINCT ...` for values loaded from its configured database.

### Databases

Each cohort refers to a key under `databases`. Credentials are read only from environment variables, never from YAML.

Supported engines:

- `clickhouse`: HTTP interface through `clickhouse-connect`
- `postgres`: PostgreSQL through `psycopg`

### Authentication

Authentication is off by default. To enable it:

```dotenv
AUTH_ENABLED=true
APP_USERS_JSON={"analyst":{"password_hash":"<sha256>","roles":["all"]}}
```

Generate a password hash:

```bash
python scripts/hash_password.py "your password"
```

For an internet-facing deployment, put the service behind your organization's SSO/reverse proxy. The built-in login is intentionally lightweight.

If a cohort has `allowed_roles`, only users with at least one matching role can open it. The special role `all` grants access to every cohort.

## Query safety and assumptions

- YAML is trusted administrator input; do not let end users edit it.
- User-selected values are passed as database parameters.
- SQL identifiers are validated before being composed into wrapper queries.
- `base_query` must be a single read-only `SELECT` or `WITH` query without a trailing semicolon.
- Sampling is performed in the database, then experiment splitting is performed in memory.
- Large requested samples consume application memory; configure `app.max_sample_size` appropriately.

## Docker

```bash
docker compose up --build
```

Mount your own YAML file in `compose.yaml` or replace `configs/example.yaml`.

## Tests

```bash
pytest -q
```

## Repository layout

```text
app.py                       Streamlit UI and orchestration
cohort_sampler/config.py     YAML parsing and validation
cohort_sampler/database.py   ClickHouse/PostgreSQL adapters
cohort_sampler/query.py      Safe wrapper-query construction
cohort_sampler/splitting.py  Balanced experiment allocation
cohort_sampler/auth.py       Optional environment-based login
configs/example.yaml         Generic configuration example
tests/                       Unit tests
```

## License

MIT
