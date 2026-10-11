"""Workout logging, history editing/deleting and body-weight logging: validation, database CRUD and routes."""

from datetime import date

import pytest

from conftest import TODAY, days_ago
from gym_app.body_weights import add_body_weight, list_body_weights
from gym_app.forms import BodyWeightEntry, WorkoutEntry, validate_body_weight, validate_workout
from gym_app.workouts import add_workout, delete_workout, get_workout, list_workouts, update_workout


def workout_form(**overrides):
    return {"exercise": "Squat", "sets": "5", "reps": "5", "weight": "60", "performed_on": TODAY.isoformat(), **overrides}


# --- Validation


def test_valid_workout():
    entry, errors = validate_workout(workout_form(exercise="  Bench Press ", weight="62.5"))
    assert errors == {}
    assert entry == WorkoutEntry("Bench Press", 5, 5, 62.5, TODAY)


def test_bodyweight_exercise_allows_zero_weight():
    entry, errors = validate_workout(workout_form(exercise="Pull-up", weight="0"))
    assert errors == {} and entry.weight == 0


@pytest.mark.parametrize("field, value, message", [
    ("exercise", "", "Enter an exercise."),
    ("exercise", "x" * 101, "Keep it under 100 characters."),
    ("sets", "0", "Sets must be between 1 and 100."),
    ("sets", "2.5", "Sets must be a whole number."),
    ("reps", "1001", "Reps must be between 1 and 1000."),
    ("weight", "-1", "Weight must be between 0 and 2000."),
    ("weight", "nan", "Weight must be between 0 and 2000."),
    ("weight", "heavy", "Weight must be a number (use 0 for bodyweight)."),
    ("performed_on", "2026-13-01", "Enter a valid date."),
    ("performed_on", "", "Enter a valid date."),
])
def test_invalid_workout_fields(field, value, message):
    entry, errors = validate_workout(workout_form(**{field: value}))
    assert entry is None
    assert errors == {field: message}


def test_future_workout_date_is_rejected():
    future = date.fromordinal(TODAY.toordinal() + 1).isoformat()
    _, errors = validate_workout(workout_form(performed_on=future))
    assert errors == {"performed_on": "Date can't be in the future."}


@pytest.mark.parametrize("value, ok", [("172.4", True), ("1500", True), ("0", False), ("1500.1", False),
                                       ("inf", False), ("abc", False), ("", False)])
def test_body_weight_validation(value, ok):
    entry, errors = validate_body_weight({"weight_lb": value, "measured_on": TODAY.isoformat()})
    assert (entry is not None) is ok
    assert ("weight_lb" in errors) is not ok


# --- Database CRUD


def test_workout_crud(app):
    with app.app_context():
        add_workout(WorkoutEntry("Squat", 5, 5, 60, date(2026, 10, 1)))
        add_workout(WorkoutEntry("Bench", 3, 8, 40, date(2026, 10, 3)))
        assert [w["exercise"] for w in list_workouts()] == ["Bench", "Squat"]  # newest date first

        squat = get_workout(1)
        assert squat == {"id": 1, "exercise": "Squat", "sets": 5, "reps": 5, "weight": 60.0, "performed_on": date(2026, 10, 1)}

        assert update_workout(1, WorkoutEntry("Front Squat", 4, 6, 50, date(2026, 10, 2)))
        assert get_workout(1)["exercise"] == "Front Squat"
        assert not update_workout(99, WorkoutEntry("X", 1, 1, 1, date(2026, 10, 2)))

        assert delete_workout(1)
        assert get_workout(1) is None
        assert not delete_workout(1)


def test_body_weights_are_newest_first(app):
    with app.app_context():
        add_body_weight(BodyWeightEntry(180, date(2026, 9, 1)))
        add_body_weight(BodyWeightEntry(178, date(2026, 10, 1)))
        add_body_weight(BodyWeightEntry(179, date(2026, 10, 1)))
        assert [e["weight_lb"] for e in list_body_weights()] == [179, 178, 180]


def test_database_rejects_bad_rows_even_without_the_form(app):
    """The schema's CHECK constraints are a second line of defence behind form validation."""
    import sqlite3

    with app.app_context():
        with pytest.raises(sqlite3.IntegrityError):
            add_workout(WorkoutEntry("Squat", 0, 5, 60, TODAY))


# --- Routes


def test_log_workout(client, query):
    response = client.post("/workouts", data=workout_form())
    assert response.status_code == 302 and response.location.endswith("/workouts")
    assert "Saved Squat." in client.get("/workouts").get_data(as_text=True)
    assert query("SELECT exercise, sets, reps, weight, performed_on FROM workouts") == [("Squat", 5, 5, 60.0, TODAY.isoformat())]


def test_invalid_workout_keeps_input_and_saves_nothing(client, query):
    response = client.post("/workouts", data=workout_form(exercise="Deadlift", reps="lots"))
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "Reps must be a whole number." in html
    assert 'value="Deadlift"' in html
    assert query("SELECT COUNT(*) FROM workouts") == [(0,)]


def test_history_lists_edits_and_deletes(client, query):
    client.post("/workouts", data=workout_form(performed_on=days_ago(2)))
    client.post("/workouts", data=workout_form(exercise="Bench Press"))
    table = client.get("/history").get_data(as_text=True).split("<tbody>")[1]  # skip the flash messages
    assert table.index("Bench Press") < table.index("Squat")

    assert 'value="Squat"' in client.get("/history/1/edit").get_data(as_text=True)
    response = client.post("/history/1/edit", data=workout_form(exercise="Front Squat", weight="50"), follow_redirects=True)
    assert "Updated Front Squat." in response.get_data(as_text=True)

    response = client.post("/history/2/delete", follow_redirects=True)
    assert "Workout deleted." in response.get_data(as_text=True)
    assert query("SELECT id, exercise, weight FROM workouts") == [(1, "Front Squat", 50.0)]


def test_invalid_edit_changes_nothing(client, query):
    client.post("/workouts", data=workout_form())
    assert client.post("/history/1/edit", data=workout_form(sets="0")).status_code == 400
    assert query("SELECT sets FROM workouts") == [(5,)]


@pytest.mark.parametrize("method, path", [
    ("get", "/history/99/edit"), ("post", "/history/99/edit"), ("post", "/history/99/delete"), ("get", "/no-such-page"),
])
def test_missing_things_are_404(client, method, path):
    response = getattr(client, method)(path, data=workout_form())
    assert response.status_code == 404
    assert "text/html" in response.content_type


def test_delete_requires_post(client):
    client.post("/workouts", data=workout_form())
    assert client.get("/history/1/delete").status_code == 405


def test_log_body_weight(client, query):
    response = client.post("/progress", data={"weight_lb": "172.4", "measured_on": TODAY.isoformat()}, follow_redirects=True)
    assert "Saved 172.4 lb." in response.get_data(as_text=True)
    assert query("SELECT weight_lb FROM body_weights") == [(172.4,)]


@pytest.mark.parametrize("path", ["/", "/workouts", "/history", "/exercises", "/progress", "/nutrition",
                                  "/nutrition/goals", "/profile"])
def test_every_page_renders(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert '<meta name="viewport"' in response.get_data(as_text=True)  # mobile-friendly layout
