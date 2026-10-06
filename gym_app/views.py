from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .forms import validate_workout
from .workouts import add_workout, delete_workout, get_workout, list_workouts, update_workout

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
        exercise_names=[e["name"] for e in EXERCISES],
    ), 400 if errors else 200


@bp.route("/history")
def history():
    return render_template("pages/history.html", workouts=list_workouts())


@bp.route("/history/<int:workout_id>/edit", methods=["GET", "POST"])
def history_edit(workout_id: int):
    workout = get_workout(workout_id)
    if workout is None:
        abort(404)

    errors = {}
    # Pre-fill the form with the saved values.
    form = {
        "exercise": workout["exercise"],
        "sets": workout["sets"],
        "reps": workout["reps"],
        "weight": f"{workout['weight']:g}",
        "performed_on": workout["performed_on"].isoformat(),
    }

    if request.method == "POST":
        entry, errors = validate_workout(request.form)
        if entry:
            if not update_workout(workout_id, entry):
                abort(404)
            flash(f"Updated {entry.exercise}.")
            return redirect(url_for("main.history"))
        form = request.form

    return render_template(
        "pages/edit_workout.html",
        workout=workout,
        form=form,
        errors=errors,
        exercise_names=[e["name"] for e in EXERCISES],
    ), 400 if errors else 200


# POST only: a plain link (GET) could be triggered by accident, e.g. by a browser prefetching it.
@bp.route("/history/<int:workout_id>/delete", methods=["POST"])
def history_delete(workout_id: int):
    if not delete_workout(workout_id):
        abort(404)
    flash("Workout deleted.")
    return redirect(url_for("main.history"))


@bp.route("/exercises")
def exercises():
    return render_template("pages/exercises.html", exercises=EXERCISES)


@bp.route("/progress")
def progress():
    return render_template("pages/progress.html")


@bp.route("/profile")
def profile():
    return render_template("pages/profile.html")
