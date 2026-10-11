"""Tests for the Progress page: charts, workout stats, strength progression and body weight.

Run with:  .venv/bin/python -m pytest  (they are unittest-style, so pytest runs them as is)
Each test uses its own temporary database, so your real data in instance/ is never touched.
"""

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from gym_app import create_app
from gym_app.body_weights import daily_series
from gym_app.charts import line_chart
from gym_app.stats import estimated_1rm, exercise_summaries, find_exercise, strength_series, workout_stats


def workout(exercise, sets, reps, weight, performed_on):
    return {"exercise": exercise, "sets": sets, "reps": reps, "weight": weight, "performed_on": performed_on}


class LineChartTests(unittest.TestCase):
    def test_no_data_gives_no_chart(self):
        self.assertIsNone(line_chart([], "kg"))

    def test_single_point_is_centred(self):
        chart = line_chart([(date(2026, 10, 1), 60)], "kg")
        self.assertEqual(len(chart.points), 1)
        self.assertEqual(chart.points[0].x, 50)
        self.assertEqual(chart.x_labels, ["1 Oct 2026"])
        self.assertEqual(chart.points[0].label, "1 Oct 2026: 60 kg")

    def test_points_span_the_width_and_higher_values_sit_higher(self):
        chart = line_chart([(date(2026, 10, 1), 30), (date(2026, 10, 3), 40), (date(2026, 10, 11), 35)], "kg")
        xs = [p.x for p in chart.points]
        self.assertEqual(xs[0], 3)
        self.assertEqual(xs[-1], 97)
        self.assertAlmostEqual(xs[1], 3 + 0.2 * 94)  # 2 of 10 days along
        self.assertLess(chart.points[1].y, chart.points[0].y)  # 40 kg is above 30 kg (SVG y points down)
        self.assertEqual(chart.x_labels, ["1 Oct 2026", "11 Oct 2026"])

    def test_axis_covers_every_value(self):
        chart = line_chart([(date(2026, 1, 1), 172.4), (date(2026, 2, 1), 168.9)], "lb")
        tick_values = [float(t.label) for t in chart.y_ticks]
        self.assertLessEqual(min(tick_values), 168.9)
        self.assertGreaterEqual(max(tick_values), 172.4)
        for point in chart.points:
            self.assertTrue(0 <= point.y <= 100)

    def test_unsorted_input_is_sorted_by_date(self):
        chart = line_chart([(date(2026, 3, 1), 50), (date(2026, 1, 1), 40)], "kg")
        self.assertEqual(chart.points[0].label, "1 Jan 2026: 40 kg")

    def test_flat_and_zero_values_still_get_a_non_negative_axis(self):
        for value in (0, 100):
            chart = line_chart([(date(2026, 1, 1), value), (date(2026, 1, 5), value)], "kg")
            tick_values = [float(t.label) for t in chart.y_ticks]
            self.assertGreaterEqual(min(tick_values), 0)
            self.assertGreater(len(tick_values), 1)
            self.assertEqual(chart.points[0].y, chart.points[1].y)


class StatsTests(unittest.TestCase):
    # Newest first, as list_workouts returns them.
    WORKOUTS = [
        workout("bench  press", 3, 5, 40, date(2026, 10, 6)),
        workout("Squat", 5, 5, 60, date(2026, 10, 6)),
        workout("Bench Press", 3, 8, 32, date(2026, 10, 4)),
        workout("Bench Press", 1, 10, 32, date(2026, 10, 4)),
        workout("Pull-up", 3, 8, 0, date(2026, 9, 28)),
        workout("Pull-up", 3, 10, 0, date(2026, 9, 25)),
    ]

    def test_exercise_names_are_grouped_ignoring_case_and_spacing(self):
        summaries = exercise_summaries(self.WORKOUTS)
        self.assertEqual([s.name for s in summaries], ["bench  press", "Squat", "Pull-up"])
        bench = find_exercise(summaries, "BENCH PRESS")
        self.assertEqual(bench.sessions, 2)  # two distinct days, three entries
        self.assertEqual((bench.best_weight, bench.best_reps), (40, 5))
        self.assertEqual(bench.last_on, date(2026, 10, 6))

    def test_best_set_breaks_weight_ties_by_reps(self):
        summaries = exercise_summaries([workout("Row", 3, 5, 50, date(2026, 1, 2)), workout("Row", 3, 8, 50, date(2026, 1, 1))])
        self.assertEqual(summaries[0].best_reps, 8)

    def test_estimated_1rm(self):
        self.assertEqual(estimated_1rm(100, 1), 100)
        self.assertAlmostEqual(estimated_1rm(100, 5), 116.666, places=2)
        self.assertEqual(find_exercise(exercise_summaries(self.WORKOUTS), "Pull-up").best_1rm, 0)

    def test_workout_stats(self):
        summaries = exercise_summaries(self.WORKOUTS)
        stats = workout_stats(self.WORKOUTS, summaries, today=date(2026, 10, 7))  # a Wednesday
        self.assertEqual(stats["training_days"], 4)
        self.assertEqual(stats["days_this_week"], 1)  # Mon 5 Oct onwards: only the 6th
        self.assertEqual(stats["entries"], 6)
        self.assertEqual(stats["sets"], 3 + 5 + 3 + 1 + 3 + 3)
        self.assertEqual(stats["volume"], 3 * 5 * 40 + 5 * 5 * 60 + 3 * 8 * 32 + 1 * 10 * 32)
        self.assertEqual(stats["most_trained"].name, "bench  press")  # tied on 2 sessions; most recent wins

    def test_workout_stats_with_no_workouts(self):
        self.assertIsNone(workout_stats([], [], date.today()))

    def test_strength_series_uses_heaviest_set_per_day(self):
        series = strength_series(self.WORKOUTS, "bench press")
        self.assertEqual(series["points"], [(date(2026, 10, 4), 32), (date(2026, 10, 6), 40)])
        self.assertEqual(series["unit"], "kg")
        self.assertEqual(series["change"], 8)
        self.assertEqual(series["since"], date(2026, 10, 4))

    def test_bodyweight_exercises_track_reps(self):
        series = strength_series(self.WORKOUTS, "pull-up")
        self.assertEqual(series["unit"], "reps")
        self.assertEqual(series["points"], [(date(2026, 9, 25), 10), (date(2026, 9, 28), 8)])
        self.assertEqual(series["change"], -2)

    def test_single_session_has_no_change(self):
        self.assertIsNone(strength_series(self.WORKOUTS, "squat")["change"])


class BodyWeightSeriesTests(unittest.TestCase):
    def test_one_point_per_day_and_last_added_wins(self):
        # Ordered as list_body_weights returns them: newest date first, newest-added first within a day.
        entries = [
            {"weight_lb": 171.0, "measured_on": date(2026, 10, 2)},
            {"weight_lb": 170.2, "measured_on": date(2026, 10, 1)},
            {"weight_lb": 172.0, "measured_on": date(2026, 10, 1)},
        ]
        self.assertEqual(daily_series(entries), [(date(2026, 10, 1), 170.2), (date(2026, 10, 2), 171.0)])

    def test_no_entries(self):
        self.assertEqual(daily_series([]), [])


class ProgressPageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({"TESTING": True, "DATABASE": str(Path(self.tmp.name) / "test.sqlite3")})
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def log_workout(self, exercise, sets, reps, weight, days_ago=0):
        day = (date.today() - timedelta(days=days_ago)).isoformat()
        response = self.client.post("/workouts", data={
            "exercise": exercise, "sets": sets, "reps": reps, "weight": weight, "performed_on": day,
        })
        self.assertEqual(response.status_code, 302)

    def log_weight(self, weight_lb, days_ago=0):
        day = (date.today() - timedelta(days=days_ago)).isoformat()
        return self.client.post("/progress", data={"weight_lb": weight_lb, "measured_on": day})

    def get_progress(self, query=""):
        response = self.client.get("/progress" + query)
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def test_empty_database_shows_empty_states(self):
        html = self.get_progress()
        self.assertIn("No workouts logged yet", html)
        self.assertIn("No body weight logged yet", html)
        self.assertNotIn('class="chart"', html)

    def test_stats_strength_chart_and_records(self):
        self.log_workout("Bench Press", 3, 8, 30, days_ago=3)
        self.log_workout("Bench Press", 3, 8, 32.5, days_ago=1)
        self.log_workout("Squat", 5, 5, 60, days_ago=1)
        html = self.get_progress()
        self.assertIn("Strength progression", html)
        self.assertIn("Personal records", html)
        self.assertIn("3,000 kg", html)  # 3·8·30 + 3·8·32.5 + 5·5·60 = 720 + 780 + 1,500
        # Default chart is the most recently trained exercise (Squat, logged after Bench on the same day).
        self.assertIn('<option value="Squat" selected>', html)
        self.assertIn("One session so far", html)

    def test_choosing_an_exercise_ignores_case(self):
        self.log_workout("Bench Press", 3, 8, 30, days_ago=3)
        self.log_workout("Bench Press", 3, 8, 32.5, days_ago=1)
        self.log_workout("Squat", 5, 5, 60)
        html = self.get_progress("?exercise=bench+press")
        self.assertIn('<option value="Bench Press" selected>', html)
        self.assertIn("+2.5 kg", html)
        self.assertEqual(html.count('class="chart-point"'), 2)

    def test_unknown_exercise_falls_back_with_a_notice(self):
        self.log_workout("Squat", 5, 5, 60)
        html = self.get_progress("?exercise=Curl")
        self.assertIn("No workouts found for “Curl”. Showing Squat instead.", html)
        self.assertIn('<option value="Squat" selected>', html)

    def test_unknown_exercise_with_no_workouts_shows_empty_state(self):
        html = self.get_progress("?exercise=Curl")
        self.assertIn("No workouts logged yet", html)

    def test_exercise_names_are_escaped(self):
        self.log_workout("<script>alert(1)</script>", 1, 1, 10)
        html = self.get_progress()
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_body_weight_chart(self):
        self.assertEqual(self.log_weight("172.4", days_ago=7).status_code, 302)
        html = self.get_progress()
        self.assertIn("Weight trend", html)
        self.assertIn("Log your weight on another day", html)
        self.log_weight("170.0")
        html = self.get_progress()
        self.assertIn("-2.4 lb", html)
        self.assertNotIn("Log your weight on another day", html)

    def test_invalid_body_weight_still_renders_the_whole_page(self):
        self.log_workout("Squat", 5, 5, 60)
        response = self.client.post("/progress", data={"weight_lb": "abc", "measured_on": date.today().isoformat()})
        self.assertEqual(response.status_code, 400)
        html = response.get_data(as_text=True)
        self.assertIn("Weight must be a number", html)
        self.assertIn("Strength progression", html)

    def test_other_pages_still_work(self):
        self.log_workout("Squat", 5, 5, 60)
        for path in ("/", "/workouts", "/history", "/history/1/edit", "/exercises", "/profile"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)


if __name__ == "__main__":
    unittest.main()
