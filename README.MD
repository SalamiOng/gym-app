# Gym App

[![Tests](https://github.com/SalamiOng/gym-app/actions/workflows/tests.yml/badge.svg)](https://github.com/SalamiOng/gym-app/actions/workflows/tests.yml)

A small personal gym tracker built with Flask and SQLite. Log your lifts, review and fix your history, track your body weight and what you eat (scan packaged foods by barcode), and see your strength progress over time on interactive charts. It works on desktop and mobile.

## Features

- **Workouts**: log an exercise with sets, reps, weight and date. Use 0 for bodyweight moves.
- **History**: browse every logged workout, newest first, and edit or delete entries.
- **Progress**:
  - Log your body weight (lb) and see a line chart of it, plus the change since your first entry.
  - Workout stats: training days, days trained this week, entries, total sets, total volume (sets × reps × weight) and your most-trained exercise.
  - Per-exercise summaries: sessions, best set, and estimated 1RM (Epley formula).
  - A strength chart for any exercise. Choose what it measures: heaviest set, best estimated 1RM, or volume per session. Bodyweight-only exercises track reps instead.
  - A training-frequency bar chart: days trained per week, including weeks you missed.
  - Date ranges for every chart: 1 month, 3 months, 1 year or all time.
  - Interactive charts: hover, tap or drag across a chart to read exact values, or focus it and use the arrow keys.
  - Every choice is in the URL (`?range=3m&exercise=Squat&metric=e1rm`), so a view can be bookmarked.
- **Nutrition**:
  - Log foods with a name, serving size, calories, protein, carbs and fat, under breakfast, lunch, dinner or snacks. Edit or delete any entry.
  - Daily calorie and macro totals, plus a subtotal for each meal.
  - Optional daily goals for calories and each macro, with how much is left (or how far over you are).
  - One day at a time: use Previous/Next or the date picker, or `?date=YYYY-MM-DD`.
  - **Barcode lookup**: type a barcode, or tap **Scan** to use your camera. The product is looked up on [Open Food Facts](https://world.openfoodfacts.org) and fills in the food form, so you can check the values and pick a meal before adding it. If the product isn't found, Open Food Facts can't be reached, or some values are missing, you get a clear message and can still enter the food by hand.
- **JSON API**: read-only endpoints for nutrition, progress chart data and barcode lookups (see below).
- **Exercises**: a starter list of common lifts.
- **Dashboard** and **Profile**: placeholder pages for now.

Exercise names are free text and matched case- and space-insensitively, so "bench press" and "Bench  Press" count as the same exercise.

Charts are server-rendered SVG with no chart library. A small script adds the tooltips, and without JavaScript the browser's own hover titles still work.

### Barcode scanning

- Supports EAN-13, EAN-8, UPC-A, UPC-E and GTIN-14. Barcodes are checked (digits, length and check digit) before any request is made.
- Values are per serving when the label lists a serving size, otherwise per 100 g.
- Camera scanning uses the browser's built-in `BarcodeDetector` where available (Chrome on Android, Edge). Other browsers (Safari, Firefox) load the [ZXing](https://github.com/zxing-js/browser) decoder from a CDN, but only when you tap Scan.
- Browsers only allow camera access on HTTPS pages or `localhost`. Elsewhere the Scan button is hidden, and typing the barcode still works.
- Open Food Facts is free and needs **no API key**. The app only sends a `User-Agent` header identifying itself.

## Getting started

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

Then open http://127.0.0.1:5000.

The SQLite database is created automatically at `instance/gym.sqlite3` on first start. It is git-ignored, so your data stays local.

### Configuration

Settings come from environment variables. Nothing secret is stored in the code.

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | `dev` | Signs session cookies (flash messages). **Set a long random value outside local development.** |
| `OPENFOODFACTS_USER_AGENT` | `GymApp/1.0 (personal fitness tracker)` | Identifies the app to Open Food Facts, as they ask. You can add contact details, e.g. `GymApp/1.0 (you@example.com)`. |

For example: `export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"`. A `.env` file is git-ignored if you keep settings in one.

## JSON API

All endpoints are read-only `GET` requests that return JSON. Errors look like `{"error": "<message>"}` with a matching HTTP status.

| Endpoint | Returns |
|---|---|
| `GET /api/nutrition?date=YYYY-MM-DD` | That day's foods, totals and goals (default: today). `400` for a bad or future date. |
| `GET /api/progress?range=1m\|3m\|1y\|all&exercise=<name>&metric=best\|e1rm\|volume` | Body-weight series, strength series and weekly training for the charts. `400` for an unknown range, `404` for an unknown exercise. |
| `GET /api/barcode/<code>` | The product from Open Food Facts. `400` invalid barcode, `404` not found, `503` Open Food Facts unavailable. |

```bash
curl "http://127.0.0.1:5000/api/barcode/3017620422003"
```

## Running tests

The tests use [pytest](https://pytest.org). Install the development requirements once:

```bash
pip install -r requirements-dev.txt
```

Then run:

```bash
python -m pytest                 # the whole suite
python -m pytest --cov           # with a coverage report
python -m pytest tests/test_barcode.py -v   # a single file
```

Each test uses its own temporary database, so your real data in `instance/` is never touched. The network is blocked during tests, and Open Food Facts responses are faked, so the suite runs offline and gives the same results every time.

What's covered:

- **Routes**: every page, form submissions, redirects, 404/405 handling and the JSON API.
- **Database CRUD**: workouts, body weights, foods and goals, including schema constraints and upgrading an older database.
- **Input validation**: workout, body-weight, food, goal and barcode validation, including edge cases like `nan`, `inf`, future dates and HTML in names.
- **Barcode lookup**: response parsing, per-serving vs per-100 g values, kJ to kcal conversion, and every network failure (timeouts, HTTP errors, bad JSON).
- **Charts and stats**: chart geometry, date ranges, strength metrics and weekly training.

### Continuous integration

[GitHub Actions](.github/workflows/tests.yml) runs the full test suite on every push and pull request, on Python 3.10 to 3.14, and uploads a coverage report.

## Project layout

```
run.py                  # entry point
requirements.txt        # runtime dependencies
requirements-dev.txt    # + pytest and pytest-cov
pyproject.toml          # pytest and coverage settings
.github/workflows/
  tests.yml             # CI: run the tests on every push and pull request
gym_app/
  __init__.py           # app factory (create_app), config, error handlers
  db.py                 # SQLite connection and schema setup
  schema.sql            # workouts, body_weights, foods and nutrition_goals tables
  views.py              # page routes
  api.py                # JSON API routes (/api/...)
  forms.py              # form validation
  workouts.py           # workout queries
  body_weights.py       # body-weight queries and summaries
  nutrition.py          # food and goal queries, daily totals
  food_lookup.py        # Open Food Facts barcode lookup
  stats.py              # workout stats, 1RM, strength metrics, chart ranges, weekly training
  charts.py             # line- and bar-chart geometry (drawn by partials/macros.html)
  navigation.py         # sidebar / bottom-nav items
  icons.py              # inline SVG icons
  templates/            # pages/ and partials/
  static/
    css/style.css
    js/barcode.js       # camera barcode scanning
    js/charts.js        # chart tooltips
tests/
  conftest.py           # fixtures: temporary app/database, network blocking, fake Open Food Facts
  test_workouts.py      # workout and body-weight validation, CRUD and routes
  test_nutrition.py     # food log, totals, meals, goals
  test_barcode.py       # barcode validation, parsing, errors, Nutrition page
  test_progress.py      # charts, stats, strength progression, body weight
  test_progress_charts.py  # ranges, metrics, training frequency, bar chart
  test_api.py           # JSON API
docs/
  progeress-log.md      # development log
```
