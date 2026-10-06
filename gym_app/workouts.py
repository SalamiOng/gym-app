from datetime import date

from .db import get_db
from .forms import WorkoutEntry

_COLUMNS = "id, exercise, sets, reps, weight, performed_on"


def _to_dict(row) -> dict:
    return {**row, "performed_on": date.fromisoformat(row["performed_on"])}


def add_workout(entry: WorkoutEntry) -> None:
    db = get_db()
    db.execute(
        "INSERT INTO workouts (exercise, sets, reps, weight, performed_on) VALUES (?, ?, ?, ?, ?)",
        (entry.exercise, entry.sets, entry.reps, entry.weight, entry.performed_on.isoformat()),
    )
    db.commit()


def list_workouts() -> list[dict]:
    rows = get_db().execute(
        f"SELECT {_COLUMNS} FROM workouts ORDER BY performed_on DESC, id DESC"
    ).fetchall()
    return [_to_dict(row) for row in rows]


def get_workout(workout_id: int) -> dict | None:
    row = get_db().execute(
        f"SELECT {_COLUMNS} FROM workouts WHERE id = ?", (workout_id,)
    ).fetchone()
    return _to_dict(row) if row else None


def update_workout(workout_id: int, entry: WorkoutEntry) -> bool:
    """Returns False if no workout has that id."""
    db = get_db()
    cursor = db.execute(
        "UPDATE workouts SET exercise = ?, sets = ?, reps = ?, weight = ?, performed_on = ?"
        " WHERE id = ?",
        (entry.exercise, entry.sets, entry.reps, entry.weight, entry.performed_on.isoformat(),
         workout_id),
    )
    db.commit()
    return cursor.rowcount > 0


def delete_workout(workout_id: int) -> bool:
    """Returns False if no workout has that id."""
    db = get_db()
    cursor = db.execute("DELETE FROM workouts WHERE id = ?", (workout_id,))
    db.commit()
    return cursor.rowcount > 0
