from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp, mannwhitneyu, ttest_ind
from sklearn.model_selection import ShuffleSplit, StratifiedShuffleSplit


def _clean(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").dropna()


def metric_comparison(control: pd.DataFrame, treatment: pd.DataFrame, column: str) -> dict[str, float]:
    c, t = _clean(control[column]), _clean(treatment[column])
    result = {
        "control_mean": c.mean(), "treatment_mean": t.mean(),
        "control_std": c.std(), "treatment_std": t.std(),
        "control_median": c.median(), "treatment_median": t.median(),
        "cohens_d": np.nan, "mann_whitney_p": np.nan, "ks_p": np.nan, "welch_t_p": np.nan,
    }
    if len(c) < 2 or len(t) < 2:
        return result
    pooled = np.sqrt((c.var() + t.var()) / 2)
    result["cohens_d"] = 0.0 if pooled == 0 else abs(c.mean() - t.mean()) / pooled
    result["mann_whitney_p"] = mannwhitneyu(c, t, alternative="two-sided").pvalue
    result["ks_p"] = ks_2samp(c, t).pvalue
    result["welch_t_p"] = ttest_ind(c, t, equal_var=False, nan_policy="omit").pvalue
    return result


def _score(frame: pd.DataFrame, control_idx: np.ndarray, treatment_idx: np.ndarray, metrics: list[str]) -> float:
    score = 0.0
    for metric in metrics:
        values = pd.to_numeric(frame[metric], errors="coerce")
        c, t = values.iloc[control_idx].dropna(), values.iloc[treatment_idx].dropna()
        if len(c) < 2 or len(t) < 2:
            continue
        pooled = np.sqrt((c.var() + t.var()) / 2)
        effect = 0 if pooled == 0 else abs(c.mean() - t.mean()) / pooled
        score += ks_2samp(c, t).pvalue + mannwhitneyu(c, t).pvalue - effect
    return score


def best_split(frame: pd.DataFrame, control_percent: int, metrics: list[str], stratify: str | None = None, iterations: int = 250) -> tuple[pd.DataFrame, int, float]:
    if len(frame) < 2:
        raise ValueError("At least two rows are required to create experiment groups")
    work = frame.reset_index(drop=True).copy()
    if stratify:
        valid = work[stratify].value_counts(dropna=False)
        if (valid < 2).any() or len(valid) < 2:
            stratify = None
    best: tuple[np.ndarray, np.ndarray] | None = None
    best_seed, best_score = 0, float("-inf")
    for seed in range(iterations):
        if stratify:
            splitter = StratifiedShuffleSplit(n_splits=1, train_size=control_percent / 100, random_state=seed)
            indices = splitter.split(work, work[stratify].fillna("<missing>"))
        else:
            splitter = ShuffleSplit(n_splits=1, train_size=control_percent / 100, random_state=seed)
            indices = splitter.split(work)
        control_idx, treatment_idx = next(indices)
        score = _score(work, control_idx, treatment_idx, metrics)
        if score > best_score:
            best, best_seed, best_score = (control_idx, treatment_idx), seed, score
    assert best is not None
    work["experiment_group"] = "Treatment"
    work.loc[best[0], "experiment_group"] = "Control"
    return work, best_seed, best_score


def comparison_table(frame: pd.DataFrame, metrics: list[tuple[str, str]]) -> pd.DataFrame:
    control = frame[frame["experiment_group"] == "Control"]
    treatment = frame[frame["experiment_group"] == "Treatment"]
    rows = []
    for label, column in metrics:
        rows.append({"metric": label, **metric_comparison(control, treatment, column)})
    return pd.DataFrame(rows)
