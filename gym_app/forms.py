from dataclasses import dataclass
from datetime import date

MAX_EXERCISE_LENGTH = 100
MAX_SETS = 100
MAX_REPS = 1000
MAX_WEIGHT = 2000
MAX_BODY_WEIGHT_LB = 1500
MAX_FOOD_NAME_LENGTH = 100
MAX_SERVING_LENGTH = 50
MAX_CALORIES = 20000
MAX_MACRO_G = 2000

# Meal keys as stored in the database, with their display labels, in display order.
MEALS = {"breakfast": "Breakfast", "lunch": "Lunch", "dinner": "Dinner", "snack": "Snacks"}

# (form field / column name, label, maximum) for each number on a food entry or goal.
NUTRIENT_FIELDS = [
    ("calories", "Calories", MAX_CALORIES),
    ("protein_g", "Protein", MAX_MACRO_G),
    ("carbs_g", "Carbs", MAX_MACRO_G),
    ("fat_g", "Fat", MAX_MACRO_G),
]


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


@dataclass
class FoodEntry:
    name: str
    serving: str
    meal: str  # a key of MEALS
    calories: float
    protein_g: float
    carbs_g: float
    fat_g: float
    eaten_on: date


@dataclass
class NutritionGoals:
    """Daily targets. None means no goal is set for that nutrient."""
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None


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


def _parse_float(value: str, label: str, maximum: float, *, allow_zero: bool = True) -> tuple[float | None, str | None]:
    try:
        number = float(value)
    except ValueError:
        return None, f"{label} must be a number."
    above_minimum = number >= 0 if allow_zero else number > 0
    if not (above_minimum and number <= maximum):  # nan fails every comparison, inf fails the maximum
        low = "between 0 and" if allow_zero else "more than 0 and at most"
        return None, f"{label} must be {low} {maximum:,}."
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


def validate_food(form) -> tuple[FoodEntry | None, dict[str, str]]:
    """Check submitted form data. Returns (entry, {}) if valid, else (None, errors by field)."""
    errors: dict[str, str] = {}

    name = form.get("name", "").strip()
    if not name:
        errors["name"] = "Enter a food name."
    elif len(name) > MAX_FOOD_NAME_LENGTH:
        errors["name"] = f"Keep it under {MAX_FOOD_NAME_LENGTH} characters."

    serving = form.get("serving", "").strip()
    if not serving:
        errors["serving"] = "Enter a serving size, e.g. 1 cup or 150 g."
    elif len(serving) > MAX_SERVING_LENGTH:
        errors["serving"] = f"Keep it under {MAX_SERVING_LENGTH} characters."

    meal = form.get("meal", "")
    if meal not in MEALS:
        errors["meal"] = "Choose a meal."

    numbers = {}
    for key, label, maximum in NUTRIENT_FIELDS:
        numbers[key], error = _parse_float(form.get(key, "").strip(), label, maximum)
        if error:
            errors[key] = error

    eaten_on, error = _parse_past_date(form.get("eaten_on", "").strip())
    if error:
        errors["eaten_on"] = error

    if errors:
        return None, errors
    return FoodEntry(name, serving, meal, eaten_on=eaten_on, **numbers), {}


def validate_goals(form) -> tuple[NutritionGoals | None, dict[str, str]]:
    """Every goal is optional: an empty box means no goal. Set goals must be more than 0."""
    errors: dict[str, str] = {}
    goals = {}
    for key, label, maximum in NUTRIENT_FIELDS:
        raw = form.get(key, "").strip()
        if not raw:
            goals[key] = None
            continue
        goals[key], error = _parse_float(raw, f"{label} goal", maximum, allow_zero=False)
        if error:
            errors[key] = error

    if errors:
        return None, errors
    return NutritionGoals(**goals), {}
