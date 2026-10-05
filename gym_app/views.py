from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .forms import validate_workout
from .workouts import add_workout, list_workouts

bp = Blueprint("main", __name__)

EXERCISES = [
    {"name": "Bench Press", "group": "Chest"},
    {"name": "Squat", "group": "Legs"},
    {"name": "Deadlift", "group": "Back"},
    {"name": "Overhead Press", "group": "Shoulders"},
    {"name": "Pull-up", "group": "Back"},
    {"name": "Barbell Row", "group": "Back"},
]


@bp.route("/")
def dashboard():
    stats = [
        {"label": "Workouts this week", "value": 0, "icon": "flame"},
        {"label": "Minutes trained", "value": 0, "icon": "timer"},
        {"label": "Personal records", "value": 0, "icon": "trophy"},
    ]
    return render_template("pages/dashboard.html", stats=stats)


@bp.route("/workouts", methods=["GET", "POST"])
def workouts():
    errors = {}
    form = {"performed_on": date.today().isoformat()}

    if request.method == "POST":
        entry, errors = validate_workout(request.form)
        if entry:
            add_workout(entry)
            flash(f"Saved {entry.exercise}.")
            # Redirect so refreshing the page doesn't submit the form again.
            return redirect(url_for("main.workouts"))
        form = request.form

    return render_template(
        "pages/workouts.html",
        form=form,
        errors=errors,
        workouts=list_workouts(),
        exercise_names=[e["name"] for e in EXERCISES],
    ), 400 if errors else 200


@bp.route("/exercises")
def exercises():
    return render_template("pages/exercises.html", exercises=EXERCISES)


@bp.route("/progress")
def progress():
    return render_template("pages/progress.html")


@bp.route("/profile")
def profile():
    return render_template("pages/profile.html")
