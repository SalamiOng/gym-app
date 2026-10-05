from dataclasses import dataclass
from datetime import date

MAX_EXERCISE_LENGTH = 100
MAX_SETS = 100
MAX_REPS = 1000
MAX_WEIGHT = 2000


@dataclass
class WorkoutEntry:
    exercise: str
    sets: int
    reps: int
    weight: float
    performed_on: date


def _parse_int(value: str, label: str, maximum: int) -> tuple[int | None, str | None]:
    try:
        number = int(value)
    except ValueError:
        return None, f"{label} must be a whole number."
    if not 1 <= number <= maximum:
        return None, f"{label} must be between 1 and {maximum}."
    return number, None


def validate_workout(form) -> tuple[WorkoutEntry | None, dict[str, str]]:
    """Check submitted form data. Returns (entry, {}) if valid, else (None, errors by field)."""
    errors: dict[str, str] = {}

    exercise = form.get("exercise", "").strip()
    if not exercise:
        errors["exercise"] = "Enter an exercise."
    elif len(exercise) > MAX_EXERCISE_LENGTH:
        errors["exercise"] = f"Keep it under {MAX_EXERCISE_LENGTH} characters."

    sets, error = _parse_int(form.get("sets", "").strip(), "Sets", MAX_SETS)
    if error:
        errors["sets"] = error

    reps, error = _parse_int(form.get("reps", "").strip(), "Reps", MAX_REPS)
    if error:
        errors["reps"] = error

    weight = None
    try:
        weight = float(form.get("weight", "").strip())
    except ValueError:
        errors["weight"] = "Weight must be a number (use 0 for bodyweight)."
    else:
        if not 0 <= weight <= MAX_WEIGHT:  # also rejects nan
            errors["weight"] = f"Weight must be between 0 and {MAX_WEIGHT}."

    performed_on = None
    try:
        performed_on = date.fromisoformat(form.get("performed_on", "").strip())
    except ValueError:
        errors["performed_on"] = "Enter a valid date."
    else:
        if performed_on > date.today():
            errors["performed_on"] = "Date can't be in the future."

    if errors:
        return None, errors
    return WorkoutEntry(exercise, sets, reps, weight, performed_on), {}
