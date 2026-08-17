import pandas as pd

from cohort_sampler.splitting import best_split, comparison_table


def test_split_assigns_every_row_once():
    frame = pd.DataFrame({"id": range(100), "segment": ["a", "b"] * 50, "value": range(100)})
    result, seed, score = best_split(frame, 50, ["value"], "segment", iterations=10)
    assert len(result) == 100
    assert set(result["experiment_group"]) == {"Control", "Treatment"}
    assert (result["experiment_group"] == "Control").sum() == 50
    summary = comparison_table(result, [("Value", "value")])
    assert summary.iloc[0]["metric"] == "Value"
