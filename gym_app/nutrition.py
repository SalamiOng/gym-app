"""Food log and daily nutrition goals: database queries plus the daily totals shown on the Nutrition page."""

from dataclasses import asdict
from datetime import date

from .db import get_db
from .forms import MEALS, NUTRIENT_FIELDS, FoodEntry, NutritionGoals

# Column names match the keys in NUTRIENT_FIELDS, so one list drives the SQL, the totals and the page.
NUTRIENT_KEYS = [key for key, _, _ in NUTRIENT_FIELDS]
UNITS = {"calories": "kcal", "protein_g": "g", "carbs_g": "g", "fat_g": "g"}

_FOOD_COLUMNS = "id, name, serving, meal, calories, protein_g, carbs_g, fat_g, eaten_on"


def _to_dict(row) -> dict:
    return {**row, "eaten_on": date.fromisoformat(row["eaten_on"])}


def _values(entry: FoodEntry) -> tuple:
    return (entry.name, entry.serving, entry.meal, entry.calories, entry.protein_g, entry.carbs_g,
            entry.fat_g, entry.eaten_on.isoformat())


# --- Food entries


def add_food(entry: FoodEntry) -> None:
    db = get_db()
    db.execute(
        "INSERT INTO foods (name, serving, meal, calories, protein_g, carbs_g, fat_g, eaten_on)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        _values(entry),
    )
    db.commit()


def list_foods(day: date) -> list[dict]:
    """Foods eaten on one day, in the order they were logged."""
    rows = get_db().execute(
        f"SELECT {_FOOD_COLUMNS} FROM foods WHERE eaten_on = ? ORDER BY id", (day.isoformat(),)
    ).fetchall()
    return [_to_dict(row) for row in rows]


def get_food(food_id: int) -> dict | None:
    row = get_db().execute(f"SELECT {_FOOD_COLUMNS} FROM foods WHERE id = ?", (food_id,)).fetchone()
    return _to_dict(row) if row else None


def update_food(food_id: int, entry: FoodEntry) -> bool:
    """Returns False if no food has that id."""
    db = get_db()
    cursor = db.execute(
        "UPDATE foods SET name = ?, serving = ?, meal = ?, calories = ?, protein_g = ?, carbs_g = ?,"
        " fat_g = ?, eaten_on = ? WHERE id = ?",
        (*_values(entry), food_id),
    )
    db.commit()
    return cursor.rowcount > 0


def delete_food(food_id: int) -> bool:
    """Returns False if no food has that id."""
    db = get_db()
    cursor = db.execute("DELETE FROM foods WHERE id = ?", (food_id,))
    db.commit()
    return cursor.rowcount > 0


# --- Goals


def get_goals() -> NutritionGoals:
    row = get_db().execute(
        "SELECT calories, protein_g, carbs_g, fat_g FROM nutrition_goals WHERE id = 1"
    ).fetchone()
    return NutritionGoals(**row) if row else NutritionGoals()


def save_goals(goals: NutritionGoals) -> None:
    """Insert the single goals row the first time, then update it in place."""
    db = get_db()
    db.execute(
        "INSERT INTO nutrition_goals (id, calories, protein_g, carbs_g, fat_g) VALUES (1, ?, ?, ?, ?)"
        " ON CONFLICT (id) DO UPDATE SET calories = excluded.calories, protein_g = excluded.protein_g,"
        " carbs_g = excluded.carbs_g, fat_g = excluded.fat_g, updated_at = CURRENT_TIMESTAMP",
        (goals.calories, goals.protein_g, goals.carbs_g, goals.fat_g),
    )
    db.commit()


# --- Daily totals


def food_totals(foods: list[dict]) -> dict[str, float]:
    # Rounded so float noise (e.g. 0.1 + 0.2 = 0.30000000000000004) never reaches the page.
    return {key: round(sum(food[key] for food in foods), 1) for key in NUTRIENT_KEYS}


def meals_for_day(foods: list[dict]) -> list[dict]:
    """Every meal in display order, each with its foods and subtotals (empty meals included)."""
    meals = []
    for key, label in MEALS.items():
        meal_foods = [food for food in foods if food["meal"] == key]
        meals.append({"key": key, "label": label, "foods": meal_foods, "totals": food_totals(meal_foods)})
    return meals


def goal_progress(totals: dict[str, float], goals: NutritionGoals) -> list[dict]:
    """One row per nutrient comparing the day's total with its goal (goal is None when not set)."""
    goal_values = asdict(goals)
    rows = []
    for key, label, _ in NUTRIENT_FIELDS:
        total, goal = totals[key], goal_values[key]
        rows.append({
            "key": key,
            "label": label,
            "unit": UNITS[key],
            "total": total,
            "goal": goal,
            # Negative when over the goal.
            "remaining": round(goal - total, 1) if goal else None,
            # Bar width, capped so going over the goal fills the bar rather than overflowing it.
            "percent": min(round(total / goal * 100), 100) if goal else 0,
        })
    return rows
