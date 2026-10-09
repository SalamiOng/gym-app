"""Tests for the Nutrition page: logging, editing and deleting foods, daily totals, meals and goals.

Run with:  .venv/bin/python -m unittest discover -s tests -v
Each test uses its own temporary database, so your real data in instance/ is never touched.
"""

import sqlite3
from contextlib import closing
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from gym_app import create_app
from gym_app.forms import NutritionGoals, validate_food, validate_goals
from gym_app.nutrition import food_totals, goal_progress, meals_for_day

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


def food_form(**overrides):
    form = {
        "name": "Greek yogurt", "serving": "1 cup", "meal": "breakfast",
        "calories": "150", "protein_g": "20", "carbs_g": "8", "fat_g": "4",
        "eaten_on": TODAY.isoformat(),
    }
    form.update(overrides)
    return form


def food(meal, calories, protein_g=0.0, carbs_g=0.0, fat_g=0.0):
    return {"meal": meal, "calories": calories, "protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g}


class ValidationTests(unittest.TestCase):
    def test_valid_food_accepts_decimals(self):
        entry, errors = validate_food(food_form(calories="152.5", protein_g="20.4"))
        self.assertEqual(errors, {})
        self.assertEqual((entry.calories, entry.protein_g, entry.eaten_on), (152.5, 20.4, TODAY))

    def test_zero_is_allowed_for_foods(self):
        entry, errors = validate_food(food_form(calories="0", protein_g="0", carbs_g="0", fat_g="0"))
        self.assertEqual(errors, {})

    def test_every_invalid_field_is_reported_at_once(self):
        _, errors = validate_food({
            "name": "  ", "serving": "", "meal": "brunch", "calories": "abc",
            "protein_g": "-1", "carbs_g": "nan", "fat_g": "inf",
            "eaten_on": (TODAY + timedelta(days=1)).isoformat(),
        })
        self.assertEqual(set(errors), {"name", "serving", "meal", "calories", "protein_g", "carbs_g", "fat_g", "eaten_on"})
        self.assertEqual(errors["calories"], "Calories must be a number.")
        self.assertEqual(errors["protein_g"], "Protein must be between 0 and 2,000.")
        self.assertEqual(errors["eaten_on"], "Date can't be in the future.")

    def test_missing_fields_are_errors(self):
        _, errors = validate_food({})
        self.assertIn("name", errors)
        self.assertIn("calories", errors)
        self.assertIn("eaten_on", errors)

    def test_too_long_text(self):
        _, errors = validate_food(food_form(name="x" * 101, serving="y" * 51))
        self.assertIn("name", errors)
        self.assertIn("serving", errors)

    def test_goals_are_optional_but_must_be_positive(self):
        goals, errors = validate_goals({"calories": "2200", "protein_g": "", "carbs_g": " ", "fat_g": "70.5"})
        self.assertEqual(errors, {})
        self.assertEqual(goals, NutritionGoals(calories=2200, protein_g=None, carbs_g=None, fat_g=70.5))

        _, errors = validate_goals({"calories": "0", "protein_g": "-5", "carbs_g": "abc", "fat_g": "999999"})
        self.assertEqual(set(errors), {"calories", "protein_g", "carbs_g", "fat_g"})
        self.assertEqual(errors["calories"], "Calories goal must be more than 0 and at most 20,000.")


class TotalsTests(unittest.TestCase):
    FOODS = [
        food("breakfast", 150, 20, 8, 4),
        food("lunch", 600.5, 35.1, 70, 18),
        food("breakfast", 90.2, 0.1, 22, 0.2),
    ]

    def test_daily_totals_are_rounded_sums(self):
        self.assertEqual(food_totals(self.FOODS), {"calories": 840.7, "protein_g": 55.2, "carbs_g": 100, "fat_g": 22.2})

    def test_no_foods_total_zero(self):
        self.assertEqual(food_totals([]), {"calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0})

    def test_meals_are_in_order_with_subtotals_and_empty_meals_kept(self):
        meals = meals_for_day(self.FOODS)
        self.assertEqual([m["key"] for m in meals], ["breakfast", "lunch", "dinner", "snack"])
        self.assertEqual(len(meals[0]["foods"]), 2)
        self.assertEqual(meals[0]["totals"]["calories"], 240.2)
        self.assertEqual(meals[2]["foods"], [])
        self.assertEqual(meals[2]["totals"]["calories"], 0)

    def test_goal_progress(self):
        rows = goal_progress(
            {"calories": 1800, "protein_g": 160, "carbs_g": 50, "fat_g": 0},
            NutritionGoals(calories=2000, protein_g=150, carbs_g=None, fat_g=70),
        )
        by_key = {row["key"]: row for row in rows}
        self.assertEqual((by_key["calories"]["remaining"], by_key["calories"]["percent"]), (200, 90))
        self.assertEqual((by_key["protein_g"]["remaining"], by_key["protein_g"]["percent"]), (-10, 100))  # over: bar capped
        self.assertEqual((by_key["carbs_g"]["goal"], by_key["carbs_g"]["remaining"]), (None, None))
        self.assertEqual(by_key["fat_g"]["percent"], 0)


class NutritionPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "test.sqlite3")
        self.app = create_app({"TESTING": True, "DATABASE": self.db_path})
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def log(self, **overrides):
        response = self.client.post("/nutrition", data=food_form(**overrides))
        self.assertEqual(response.status_code, 302)
        return response

    def page(self, query=""):
        response = self.client.get("/nutrition" + query)
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def rows(self):
        with closing(sqlite3.connect(self.db_path)) as db:
            return db.execute("SELECT name, meal, calories, eaten_on FROM foods ORDER BY id").fetchall()

    def test_empty_day(self):
        html = self.page()
        self.assertIn("Nothing logged for this day", html)
        self.assertIn("Today", html)
        self.assertEqual(html.count("No goal set"), 4)
        self.assertIn('<option value="breakfast" selected>', html)
        self.assertIn(f'value="{TODAY.isoformat()}"', html)

    def test_log_food_shows_it_under_its_meal_with_totals(self):
        response = self.client.post("/nutrition", data=food_form(meal="snack"), follow_redirects=True)
        html = response.get_data(as_text=True)
        self.assertIn("Added Greek yogurt to snacks.", html)
        self.assertIn("Nothing logged for breakfast.", html)
        self.assertIn("1 cup", html)
        self.log(name="Chicken wrap", serving="1 wrap", meal="lunch", calories="1050.5", protein_g="40.25")
        html = self.page()
        self.assertIn("1,200.5<small> kcal</small>", html)  # 150 + 1050.5
        self.assertIn("60.2<small> g</small>", html)  # 20 + 40.25, one decimal place
        self.assertEqual(self.rows(), [("Greek yogurt", "snack", 150.0, TODAY.isoformat()),
                                       ("Chicken wrap", "lunch", 1050.5, TODAY.isoformat())])

    def test_invalid_food_shows_errors_and_keeps_input(self):
        response = self.client.post("/nutrition", data=food_form(name="Toast", calories="lots", meal="dinner"))
        self.assertEqual(response.status_code, 400)
        html = response.get_data(as_text=True)
        self.assertIn("Calories must be a number.", html)
        self.assertIn('value="Toast"', html)
        self.assertIn('<option value="dinner" selected>', html)
        self.assertEqual(self.rows(), [])

    def test_days_are_separate_and_navigable(self):
        self.log(name="Oats", eaten_on=YESTERDAY.isoformat())
        self.assertIn("Nothing logged for this day", self.page())
        html = self.page(f"?date={YESTERDAY.isoformat()}")
        self.assertIn("Oats", html)
        self.assertIn("Yesterday", html)
        self.assertIn('href="/nutrition"', html)  # "Next" goes back to today
        self.assertIn('class="btn btn-sm is-disabled"', self.page())  # no "Next" from today

    def test_logging_for_another_day_redirects_to_that_day(self):
        response = self.log(eaten_on=YESTERDAY.isoformat())
        self.assertTrue(response.location.endswith(f"/nutrition?date={YESTERDAY.isoformat()}"))

    def test_bad_or_future_date_in_url_falls_back_to_today(self):
        self.assertIn("isn&#39;t a valid date. Showing today instead.", self.page("?date=banana"))
        future = (TODAY + timedelta(days=3)).isoformat()
        self.assertIn("You can&#39;t view future days.", self.page(f"?date={future}"))

    def test_edit_food(self):
        self.log()
        html = self.client.get("/nutrition/1/edit").get_data(as_text=True)
        self.assertIn('value="Greek yogurt"', html)
        self.assertIn('value="150"', html)
        self.assertIn('<option value="breakfast" selected>', html)

        response = self.client.post("/nutrition/1/edit", data=food_form(name="Skyr", meal="dinner", calories="120.5"),
                                    follow_redirects=True)
        self.assertIn("Updated Skyr.", response.get_data(as_text=True))
        self.assertEqual(self.rows(), [("Skyr", "dinner", 120.5, TODAY.isoformat())])

    def test_invalid_edit_changes_nothing(self):
        self.log()
        response = self.client.post("/nutrition/1/edit", data=food_form(name="", fat_g="-3"))
        self.assertEqual(response.status_code, 400)
        html = response.get_data(as_text=True)
        self.assertIn("Enter a food name.", html)
        self.assertIn("Fat must be between 0 and 2,000.", html)
        self.assertEqual(self.rows(), [("Greek yogurt", "breakfast", 150.0, TODAY.isoformat())])

    def test_delete_food_returns_to_its_day(self):
        self.log(eaten_on=YESTERDAY.isoformat())
        self.log(name="Banana")
        response = self.client.post("/nutrition/1/delete")
        self.assertTrue(response.location.endswith(f"?date={YESTERDAY.isoformat()}"))
        self.assertEqual(self.rows(), [("Banana", "breakfast", 150.0, TODAY.isoformat())])

    def test_delete_needs_post_and_missing_ids_404(self):
        self.log()
        self.assertEqual(self.client.get("/nutrition/1/delete").status_code, 405)
        self.assertEqual(self.client.get("/nutrition/99/edit").status_code, 404)
        self.assertEqual(self.client.post("/nutrition/99/edit", data=food_form()).status_code, 404)
        self.assertEqual(self.client.post("/nutrition/99/delete").status_code, 404)
        self.assertEqual(len(self.rows()), 1)

    def test_goals_set_update_and_clear(self):
        html = self.client.get("/nutrition/goals").get_data(as_text=True)
        self.assertIn("Daily goals", html)

        response = self.client.post("/nutrition/goals", data={"calories": "2000", "protein_g": "150", "carbs_g": "", "fat_g": ""},
                                    follow_redirects=True)
        html = response.get_data(as_text=True)
        self.assertIn("Goals saved.", html)
        self.assertIn("of 2,000 kcal", html)
        self.assertIn("2,000 left", html)
        self.assertEqual(html.count("No goal set"), 2)

        self.log(protein_g="170")
        html = self.page()
        self.assertIn("1,850 left", html)
        self.assertIn('<strong class="over">20 over</strong>', html)

        # The form shows saved goals; saving again updates the single row instead of adding one.
        self.assertIn('value="2000"', self.client.get("/nutrition/goals").get_data(as_text=True))
        self.client.post("/nutrition/goals", data={"calories": "", "protein_g": "", "carbs_g": "", "fat_g": ""})
        self.assertEqual(self.page().count("No goal set"), 4)
        with closing(sqlite3.connect(self.db_path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM nutrition_goals").fetchone()[0], 1)

    def test_invalid_goals_keep_old_goals(self):
        self.client.post("/nutrition/goals", data={"calories": "2000"})
        response = self.client.post("/nutrition/goals", data={"calories": "-1", "protein_g": "abc"})
        self.assertEqual(response.status_code, 400)
        html = response.get_data(as_text=True)
        self.assertIn("Calories goal must be more than 0", html)
        self.assertIn("Protein goal must be a number.", html)
        self.assertIn("of 2,000 kcal", self.page())

    def test_goals_page_returns_to_the_day_you_came_from(self):
        response = self.client.post(f"/nutrition/goals?date={YESTERDAY.isoformat()}", data={"calories": "2000"})
        self.assertTrue(response.location.endswith(f"/nutrition?date={YESTERDAY.isoformat()}"))

    def test_food_names_are_escaped(self):
        self.log(name="<script>alert(1)</script>")
        html = self.page()
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_data_survives_a_restart(self):
        self.log()
        self.client.post("/nutrition/goals", data={"calories": "2000"})
        restarted = create_app({"TESTING": True, "DATABASE": self.db_path}).test_client()
        html = restarted.get("/nutrition").get_data(as_text=True)
        self.assertIn("Greek yogurt", html)
        self.assertIn("of 2,000 kcal", html)

    def test_existing_database_is_upgraded_without_losing_data(self):
        # A database from before this feature: only the older tables, with data in them.
        old_db = str(Path(self.tmp.name) / "old.sqlite3")
        with closing(sqlite3.connect(old_db)) as db:
            db.executescript("""
                CREATE TABLE workouts (id INTEGER PRIMARY KEY AUTOINCREMENT, exercise TEXT NOT NULL,
                    sets INTEGER NOT NULL, reps INTEGER NOT NULL, weight REAL NOT NULL, performed_on TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
                INSERT INTO workouts (exercise, sets, reps, weight, performed_on) VALUES ('Squat', 5, 5, 60, '2026-10-01');
            """)
        client = create_app({"TESTING": True, "DATABASE": old_db}).test_client()
        self.assertIn("Squat", client.get("/history").get_data(as_text=True))
        self.assertEqual(client.get("/nutrition").status_code, 200)

    def test_workout_and_progress_pages_still_work(self):
        self.client.post("/workouts", data={"exercise": "Squat", "sets": 5, "reps": 5, "weight": 60,
                                            "performed_on": TODAY.isoformat()})
        self.client.post("/progress", data={"weight_lb": "172.4", "measured_on": TODAY.isoformat()})
        self.log()
        for path in ("/", "/workouts", "/history", "/history/1/edit", "/exercises", "/progress", "/profile",
                     "/nutrition", "/nutrition/1/edit", "/nutrition/goals"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)
        self.assertIn("Squat", self.client.get("/history").get_data(as_text=True))
        self.assertIn("172.4 lb", self.client.get("/progress").get_data(as_text=True))

    def test_nutrition_is_in_the_menu(self):
        html = self.page()
        self.assertIn('href="/nutrition"', html)
        self.assertIn('aria-current="page"', html)


if __name__ == "__main__":
    unittest.main()
