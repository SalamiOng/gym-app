"""Interactive Progress charts: date ranges, strength metrics, training frequency and the bar chart."""

from datetime import date

import pytest

from conftest import days_ago
from gym_app.charts import bar_chart
from gym_app.stats import range_start, strength_series, weekly_training


def workout(exercise, sets, reps, weight, performed_on):
    return {"exercise": exercise, "sets": sets, "reps": reps, "weight": weight, "performed_on": performed_on}


# Newest first, as list_workouts returns them.
WORKOUTS = [
    workout("Bench Press", 3, 5, 50, date(2026, 10, 6)),
    workout("Bench Press", 2, 10, 40, date(2026, 10, 6)),
    workout("Bench Press", 3, 8, 45, date(2026, 9, 1)),
    workout("Pull-up", 3, 10, 0, date(2026, 10, 5)),
    workout("Pull-up", 4, 8, 0, date(2026, 9, 2)),
]


# --- Ranges


@pytest.mark.parametrize("key, expected", [
    ("1m", date(2026, 9, 11)), ("3m", date(2026, 7, 12)), ("1y", date(2025, 10, 11)), ("all", None), ("bogus", None),
])
def test_range_start(key, expected):
    assert range_start(key, date(2026, 10, 10)) == expected


# --- Strength metrics


def test_best_metric_is_heaviest_set_per_day():
    series = strength_series(WORKOUTS, "bench press")
    assert series["points"] == [(date(2026, 9, 1), 45), (date(2026, 10, 6), 50)]
    assert series["metric_key"] == "best" and series["unit"] == "kg"
    assert [key for key, _ in series["metrics"]] == ["best", "e1rm", "volume"]


def test_e1rm_metric_takes_the_best_estimate_per_day():
    series = strength_series(WORKOUTS, "bench press", "e1rm")
    # 6 Oct: 50×5 → 58.3, 40×10 → 53.3. 1 Sep: 45×8 → 57.
    assert series["points"] == [(date(2026, 9, 1), 57), (date(2026, 10, 6), 58.3)]
    assert series["change"] == 1.3


def test_volume_metric_adds_up_every_set_in_a_day():
    series = strength_series(WORKOUTS, "bench press", "volume")
    assert series["points"] == [(date(2026, 9, 1), 1080), (date(2026, 10, 6), 750 + 800)]


def test_bodyweight_exercises_offer_reps_metrics_only():
    series = strength_series(WORKOUTS, "pull-up", "e1rm")  # not available: falls back to best
    assert series["metric_key"] == "best" and series["unit"] == "reps"
    assert [key for key, _ in series["metrics"]] == ["best", "volume"]
    assert strength_series(WORKOUTS, "pull-up", "volume")["points"] == [(date(2026, 9, 2), 32), (date(2026, 10, 5), 30)]


def test_unknown_metric_falls_back_to_best():
    assert strength_series(WORKOUTS, "bench press", "nonsense")["metric_key"] == "best"


def test_since_drops_older_sessions_but_keeps_the_unit():
    series = strength_series(WORKOUTS, "bench press", since=date(2026, 10, 1))
    assert series["points"] == [(date(2026, 10, 6), 50)]
    assert series["change"] is None

    empty = strength_series(WORKOUTS, "bench press", since=date(2026, 10, 7))
    assert (empty["points"], empty["since"], empty["change"], empty["unit"]) == ([], None, None, "kg")


# --- Weekly training


def test_weekly_training_includes_empty_weeks():
    weeks = weekly_training(WORKOUTS, today=date(2026, 10, 10), since=None)
    assert weeks[0]["week_start"] == date(2026, 8, 31)  # the Monday of the first workout's week
    assert weeks[-1]["week_start"] == date(2026, 10, 5)
    assert len(weeks) == 6
    assert (weeks[0]["days"], weeks[0]["sets"]) == (2, 7)  # 1 and 2 Sep
    assert (weeks[-1]["days"], weeks[-1]["sets"]) == (2, 8)  # 5 and 6 Oct
    assert all(w["days"] == 0 for w in weeks[1:-1])


def test_weekly_training_respects_the_range_and_cap():
    weeks = weekly_training(WORKOUTS, today=date(2026, 10, 10), since=date(2026, 9, 11))
    assert weeks[0]["week_start"] == date(2026, 9, 7)
    long_ago = [workout("Squat", 1, 1, 1, date(2020, 1, 1))]
    assert len(weekly_training(long_ago, today=date(2026, 10, 10), since=None)) == 52


def test_weekly_training_with_no_workouts():
    assert weekly_training([], date(2026, 10, 10), None) == []


# --- Bar chart geometry


def test_bar_chart_layout():
    chart = bar_chart([("a", 0, "zero"), ("b", 2, "two"), ("c", 4, "four")])
    assert [b.x for b in chart.bars] == [16.667, 50, 83.333]
    assert chart.bars[0].y == chart.baseline  # an empty week has no height
    assert chart.bars[2].y < chart.bars[1].y < chart.baseline  # taller bars reach higher (y points down)
    assert chart.y_ticks[0].label == "0"
    assert chart.x_labels == ["a", "c"]


def test_bar_chart_edge_cases():
    assert bar_chart([]) is None
    single = bar_chart([("only", 0, "none")])
    assert single.x_labels == ["only"]
    assert single.bars[0].x == 50


# --- Progress page


@pytest.fixture
def trained(client):
    for exercise, weight, ago in [("Bench Press", 40, 120), ("Bench Press", 50, 20), ("Bench Press", 55, 5), ("Squat", 60, 2)]:
        client.post("/workouts", data={"exercise": exercise, "sets": 3, "reps": 5, "weight": weight, "performed_on": days_ago(ago)})
    client.post("/progress", data={"weight_lb": "180", "measured_on": days_ago(200)})
    return client


def page(client, query=""):
    response = client.get("/progress" + query)
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_range_tabs_keep_the_other_choices(trained):
    html = page(trained, "?exercise=Bench+Press&metric=e1rm&range=1m")
    assert 'class="segment active"' in html and 'aria-current="true">1M</a>' in html
    assert 'href="/progress?range=3m&amp;exercise=Bench+Press&amp;metric=e1rm"' in html
    assert 'href="/progress?exercise=Bench+Press&amp;metric=e1rm"' in html  # "All" is the default, so it's left out
    assert '<input type="hidden" name="range" value="1m" />' in html
    assert '<option value="e1rm" selected>' in html


def test_range_limits_the_charts(trained):
    assert page(trained, "?exercise=Bench+Press").count('class="chart-point"') == 3 + 1  # strength + body weight
    html = page(trained, "?exercise=Bench+Press&range=1m")
    assert html.count('class="chart-point"') == 2
    assert "+5 kg" in html
    assert "No weigh-ins in the last month." in html


def test_no_sessions_in_range(trained):
    trained.post("/workouts", data={"exercise": "Deadlift", "sets": 1, "reps": 5, "weight": 100, "performed_on": days_ago(150)})
    html = page(trained, "?exercise=Deadlift&range=3m")
    assert "No Deadlift sessions in the last 3 months." in html
    assert 'href="/progress?exercise=Deadlift" class="link">Show all time</a>' in html
    assert "One session in the last month." in page(trained, "?exercise=Squat&range=1m")


def test_training_frequency_chart(trained):
    html = page(trained, "?range=1m")
    assert "Training frequency" in html
    assert html.count('class="chart-bar"') == 5
    assert 'data-tip="Week of ' in html
    assert ": 0 days, 0 sets" in html  # empty weeks are still shown


def test_bad_range_falls_back_to_all(trained):
    html = page(trained, "?range=forever")
    assert 'aria-current="true">All</a>' in html


def test_charts_are_interactive_and_accessible(trained):
    html = page(trained)
    assert "js/charts.js" in html
    assert 'class="chart-plot" tabindex="0" role="img"' in html
    assert 'data-tip="' in html and 'aria-live="polite"' in html
