# Progress Log

## 2026-10-08: Nutrition tracking (uncommitted)

- Added a Nutrition page: log foods (name, serving size, calories, protein, carbs, fat) under breakfast, lunch, dinner or snacks.
- Added editing and deleting of food entries (delete is POST-only, like workouts).
- Added daily totals and per-meal subtotals, one day at a time (`?date=YYYY-MM-DD`, Previous/Next, date picker).
- Added optional daily goals for calories and macros on `/nutrition/goals`, with "left" / "over" and a progress bar.
- New tables `foods` and `nutrition_goals` (a single row); existing databases get them automatically on start.
- New module `nutrition.py`; new `select_field` macro; added a Nutrition tab to the menu.
- Added `tests/test_nutrition.py` (28 tests). All 53 tests pass.

## 2026-10-07: Progress page charts and stats (uncommitted)

- Added a body-weight line chart (one point per day; the last entry added wins).
- Added workout stats: training days, days this week, entries, total sets, total volume and most-trained exercise.
- Added per-exercise summaries with best set and estimated 1RM (Epley).
- Added a strength-progression chart per exercise, chosen with `?exercise=<name>`. It shows the heaviest set per session, or most reps for bodyweight-only exercises.
- New modules: `stats.py` (calculations) and `charts.py` (SVG chart geometry, rendered by a `line_chart` macro).
- Added the first test suite, `tests/test_progress.py` (25 tests, all passing).

## 2026-10-06: Weight tracker

- Added a `body_weights` table and a body-weight logging form on the Progress page.
- Showed the latest weight and the change since the first entry.
- Moved shared workout form fields into a partial.

## 2026-10-05: Workout history

- Added a History page listing all workouts.
- Added editing and deleting of workouts. Delete is POST-only so it can't be triggered by a link prefetch.

## 2026-10-04: Workout logging

- Added the SQLite database with a `workouts` table, created automatically on start.
- Added the workout logging form with validation (no future dates, sensible limits).
- Created the README and this progress log.

## 2026-10-03: Initial setup

- Set up the Flask app with Dashboard, Workouts, Exercises, Progress and Profile pages.
- Added a sidebar, mobile bottom nav, icons and base styling.

## Next up

- Make the Dashboard show real data (it still shows placeholder zeros).
- Make the Profile page save settings, including the kg/lb unit choice.
