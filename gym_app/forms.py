from dataclasses import dataclass
from datetime import date

MAX_EXERCISE_LENGTH = 100
MAX_SETS = 100
MAX_REPS = 1000
MAX_WEIGHT = 2000
MAX_BODY_WEIGHT_LB = 1500


@dataclass
class WorkoutEntry:
    exercise: str
    sets: int
    reps: int
    weight: float
    performed_on: date


@dataclass
class BodyWeightEntry:
    weight_lb: float
    measured_on: date


def _parse_past_date(value: str) -> tuple[date | None, str | None]:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None, "Enter a valid date."
    if parsed > date.today():
        return None, "Date can't be in the future."
    return parsed, None


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

    performed_on, error = _parse_past_date(form.get("performed_on", "").strip())
    if error:
        errors["performed_on"] = error

    if errors:
        return None, errors
    return WorkoutEntry(exercise, sets, reps, weight, performed_on), {}


def validate_body_weight(form) -> tuple[BodyWeightEntry | None, dict[str, str]]:
    """Check submitted form data. Returns (entry, {}) if valid, else (None, errors by field)."""
    errors: dict[str, str] = {}

    weight_lb = None
    try:
        weight_lb = float(form.get("weight_lb", "").strip())
    except ValueError:
        errors["weight_lb"] = "Weight must be a number, e.g. 172.4."
    else:
        if not 0 < weight_lb <= MAX_BODY_WEIGHT_LB:  # also rejects nan and inf
            errors["weight_lb"] = f"Weight must be more than 0 and at most {MAX_BODY_WEIGHT_LB} lb."

    measured_on, error = _parse_past_date(form.get("measured_on", "").strip())
    if error:
        errors["measured_on"] = error

    if errors:
        return None, errors
    return BodyWeightEntry(weight_lb, measured_on), {}
