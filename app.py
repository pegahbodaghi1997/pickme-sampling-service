from __future__ import annotations

from datetime import date, timedelta
import os

from dotenv import load_dotenv
import pandas as pd
import streamlit as st

from cohort_sampler.auth import authenticate, enabled as auth_enabled
from cohort_sampler.config import Cohort, load_settings
from cohort_sampler.database import Database
from cohort_sampler.query import build_query
from cohort_sampler.splitting import best_split, comparison_table

load_dotenv()


@st.cache_resource
def settings():
    return load_settings(os.getenv("SAMPLER_CONFIG", "configs/example.yaml"))


@st.cache_resource
def database(name: str) -> Database:
    return Database.from_config(settings().databases[name])


@st.cache_data(ttl=600, show_spinner=False)
def filter_values(database_name: str, query: str) -> list:
    frame = database(database_name).query(query)
    return [] if frame.empty else frame.iloc[:, 0].dropna().tolist()


def login() -> None:
    if not auth_enabled():
        st.session_state.setdefault("roles", ["all"])
        return
    if st.session_state.get("roles"):
        return
    st.title(settings().app.get("title", "Cohort Sampler"))
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)
    if submitted:
        roles = authenticate(username, password)
        if roles:
            st.session_state["roles"] = roles
            st.session_state["username"] = username
            st.rerun()
        st.error("Invalid username or password")
    st.stop()


def allowed(cohort: Cohort) -> bool:
    roles = set(st.session_state.get("roles", []))
    return "all" in roles or bool(roles.intersection(cohort.allowed_roles))


def metric_bounds(cohort: Cohort, db: Database, selections: dict, dates) -> dict[str, tuple[float, float]]:
    bounds: dict[str, tuple[float, float]] = {}
    for metric in cohort.metrics:
        if metric.default_max is not None:
            high = metric.default_max
        else:
            sql = f"SELECT max(source.{metric.column}) AS maximum FROM ({cohort.base_query}) AS source"
            frame = db.query(sql)
            value = frame.iloc[0, 0] if not frame.empty else 100
            high = float(value) if pd.notna(value) else 100
        low = float(metric.default_min)
        if metric.step == 1:
            low, high = int(low), max(int(high), int(low) + 1)
        bounds[metric.key] = (low, high)
    return bounds


def render_cohort(cohort: Cohort) -> None:
    db = database(cohort.database)
    st.header(cohort.title)
    if cohort.description:
        st.caption(cohort.description)
    selected: dict[str, list] = {}
    dates = None
    if cohort.date_filter:
        c1, c2 = st.columns(2)
        start = c1.date_input(f"{cohort.date_filter.label}: from", value=date.today() - timedelta(days=30))
        end = c2.date_input(f"{cohort.date_filter.label}: to", value=date.today(), min_value=start)
        dates = (start, end)
    if cohort.filters:
        st.subheader("Filters")
        columns = st.columns(min(3, len(cohort.filters)))
        for index, item in enumerate(cohort.filters):
            options = item.values or filter_values(cohort.database, item.values_query or "")
            selected[item.key] = columns[index % len(columns)].multiselect(item.label, options)
    st.subheader("Metric ranges")
    defaults = metric_bounds(cohort, db, selected, dates)
    metric_ranges: dict[str, tuple[float, float]] = {}
    for metric in cohort.metrics:
        low, high = defaults[metric.key]
        metric_ranges[metric.key] = st.slider(metric.label, min_value=low, max_value=high, value=(low, high), step=metric.step)
    max_sample = int(settings().app.get("max_sample_size", 100000))
    sample_size = st.number_input("Sample size", min_value=1, max_value=max_sample, value=min(1000, max_sample))
    mode = st.radio("Output", ["Single sample", "Experiment groups"], horizontal=True)
    control_percent, stratify = 50, None
    if mode == "Experiment groups":
        c1, c2 = st.columns(2)
        control_percent = c1.slider("Control group (%)", 1, 99, 50)
        options = {"No stratification": None, **{s.label: s.column for s in cohort.stratify_columns}}
        stratify = options[c2.selectbox("Stratify by", list(options))]
    count_sql, count_params = build_query(cohort, db, selected, metric_ranges, dates, count_only=True)
    sample_sql, sample_params = build_query(cohort, db, selected, metric_ranges, dates, int(sample_size))
    c1, c2 = st.columns(2)
    if c1.button("Preview matching rows", use_container_width=True):
        with st.spinner("Counting matching rows..."):
            count = int(db.query(count_sql, count_params).iloc[0, 0])
        st.info(f"{count:,} rows match the current filters.")
    if c2.button("Generate sample", type="primary", use_container_width=True):
        with st.spinner("Generating sample..."):
            frame = db.query(sample_sql, sample_params)
        if frame.empty:
            st.warning("No rows matched the current filters.")
            return
        summary = None
        if mode == "Experiment groups":
            metric_columns = [m.column for m in cohort.metrics]
            frame, seed, score = best_split(frame, control_percent, metric_columns, stratify, int(settings().app.get("split_iterations", 250)))
            summary = comparison_table(frame, [(m.label, m.column) for m in cohort.metrics])
            st.success(f"Balanced split selected (seed {seed}, score {score:.3f}).")
        st.dataframe(frame, use_container_width=True)
        st.download_button("Download sample CSV", frame.to_csv(index=False), f"{cohort.key}_sample.csv", "text/csv")
        if summary is not None:
            st.subheader("Balance diagnostics")
            st.dataframe(summary, use_container_width=True)
            st.download_button("Download diagnostics CSV", summary.to_csv(index=False), f"{cohort.key}_diagnostics.csv", "text/csv")


def main() -> None:
    # Streamlit requires page configuration to be the first UI command.
    st.set_page_config(page_title="Cohort Sampler", page_icon="🎯", layout="wide")
    cfg = settings()
    color = cfg.app.get("primary_color", "#4f46e5")
    st.markdown(f"<style>.stButton button[kind='primary']{{background:{color};border-color:{color}}}</style>", unsafe_allow_html=True)
    login()
    st.title(cfg.app.get("title", "Cohort Sampler"))
    st.caption(cfg.app.get("subtitle", "Create reproducible samples and balanced experiment groups"))
    visible = [item for item in cfg.cohorts if allowed(item)]
    if not visible:
        st.error("Your account does not have access to any configured cohort.")
        return
    selected_title = st.sidebar.radio("Cohort", [item.title for item in visible])
    if auth_enabled() and st.sidebar.button("Sign out"):
        st.session_state.clear()
        st.rerun()
    render_cohort(next(item for item in visible if item.title == selected_title))


if __name__ == "__main__":
    main()
