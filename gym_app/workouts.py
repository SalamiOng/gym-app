from datetime import date

from .db import get_db
from .forms import WorkoutEntry


def add_workout(entry: WorkoutEntry) -> None:
    db = get_db()
    db.execute(
        "INSERT INTO workouts (exercise, sets, reps, weight, performed_on) VALUES (?, ?, ?, ?, ?)",
        (entry.exercise, entry.sets, entry.reps, entry.weight, entry.performed_on.isoformat()),
    )
    db.commit()


def list_workouts() -> list[dict]:
    rows = get_db().execute(
        "SELECT id, exercise, sets, reps, weight, performed_on"
        " FROM workouts ORDER BY performed_on DESC, id DESC"
    ).fetchall()
    return [{**row, "performed_on": date.fromisoformat(row["performed_on"])} for row in rows]
