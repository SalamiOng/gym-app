# Gym App

A small personal gym tracker built with Flask and SQLite. Log your lifts, review and fix your history, track your body weight, and see your strength progress over time.

## Features

- **Workouts**: log an exercise with sets, reps, weight and date. Use 0 for bodyweight moves.
- **History**: browse every logged workout, newest first, and edit or delete entries.
- **Progress**:
  - Log your body weight (lb) and see a line chart of it, plus the change since your first entry.
  - Workout stats: training days, days trained this week, entries, total sets, total volume (sets × reps × weight) and your most-trained exercise.
  - Per-exercise summaries: sessions, best set, and estimated 1RM (Epley formula).
  - A strength chart for any exercise, showing your heaviest set per session, or most reps for bodyweight-only exercises. Choose the exercise with `?exercise=<name>`.
- **Exercises**: a starter list of common lifts.
- **Dashboard** and **Profile**: placeholder pages for now.

Exercise names are free text and matched case- and space-insensitively, so "bench press" and "Bench  Press" count as the same exercise. Charts are drawn as server-rendered SVG, with no JavaScript or chart library.

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

Outside local development, set a real `SECRET_KEY` environment variable (it defaults to `dev`).

## Running tests

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Each test uses its own temporary database, so your real data in `instance/` is never touched.

## Project layout

```
run.py                  # entry point
gym_app/
  __init__.py           # app factory (create_app)
  db.py                 # SQLite connection and schema setup
  schema.sql            # workouts and body_weights tables
  views.py              # routes
  forms.py              # form validation
  workouts.py           # workout queries
  body_weights.py       # body-weight queries and summaries
  stats.py              # workout stats, 1RM, strength series
  charts.py             # line-chart geometry (drawn by partials/macros.html)
  navigation.py         # sidebar / bottom-nav items
  icons.py              # inline SVG icons
  templates/            # pages/ and partials/
  static/               # CSS and favicon
tests/
  test_progress.py      # charts, stats, strength progression, body weight
docs/
  progeress-log.md      # development log
```
