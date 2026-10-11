"""Read-only JSON API under /api, built on the same queries and calculations as the pages.

Errors are JSON too: {"error": "<message>"} with a matching HTTP status.
"""

from dataclasses import asdict
from datetime import date

from flask import Blueprint, current_app, jsonify, request

from .body_weights import daily_series, list_body_weights
from .food_lookup import InvalidBarcode, LookupUnavailable, ProductNotFound, lookup_barcode
from .nutrition import food_totals, get_goals, list_foods
from .stats import DEFAULT_RANGE, RANGES, exercise_summaries, find_exercise, range_start, strength_series, weekly_training
from .workouts import list_workouts

bp = Blueprint("api", __name__, url_prefix="/api")


def error(message: str, status: int):
    return jsonify(error=message), status


def _day_param() -> date:
    """?date=YYYY-MM-DD, defaulting to today. Raises ValueError with a message for bad or future dates."""
    raw = request.args.get("date", "").strip()
    if not raw:
        return date.today()
    try:
        day = date.fromisoformat(raw)
    except ValueError:
        raise ValueError("date must be YYYY-MM-DD.") from None
    if day > date.today():
        raise ValueError("date can't be in the future.")
    return day


@bp.get("/barcode/<code>")
def barcode(code: str):
    try:
        product = lookup_barcode(code, current_app.config["OPENFOODFACTS_USER_AGENT"])
    except InvalidBarcode as exc:
        return error(str(exc), 400)
    except ProductNotFound as exc:
        return error(str(exc), 404)
    except LookupUnavailable as exc:
        return error(str(exc), 503)
    return jsonify(product=product.to_dict())


@bp.get("/nutrition")
def nutrition():
    try:
        day = _day_param()
    except ValueError as exc:
        return error(str(exc), 400)
    foods = list_foods(day)
    return jsonify(
        date=day.isoformat(),
        foods=[{**food, "eaten_on": food["eaten_on"].isoformat()} for food in foods],
        totals=food_totals(foods),
        goals=asdict(get_goals()),
    )


@bp.get("/progress")
def progress():
    """Chart data for the Progress page. Query: range (1m, 3m, 1y, all), exercise (name), metric (best, e1rm, volume)."""
    range_key = request.args.get("range", DEFAULT_RANGE)
    if range_key not in RANGES:
        return error(f"range must be one of: {', '.join(RANGES)}.", 400)
    today = date.today()
    since = range_start(range_key, today)
    workouts = list_workouts()
    exercises = exercise_summaries(workouts)

    requested = request.args.get("exercise", "").strip()
    selected = find_exercise(exercises, requested) if requested else (exercises[0] if exercises else None)
    if requested and selected is None:
        return error(f"No workouts found for {requested!r}.", 404)
    strength = strength_series(workouts, selected.key, request.args.get("metric", "best"), since) if selected else None

    return jsonify(
        range=range_key,
        since=since.isoformat() if since else None,
        body_weight=[{"date": day.isoformat(), "weight_lb": weight}
                     for day, weight in daily_series(list_body_weights()) if not since or day >= since],
        strength=None if strength is None else {
            "exercise": selected.name,
            "metric": strength["metric_key"],
            "unit": strength["unit"],
            "points": [{"date": day.isoformat(), "value": value} for day, value in strength["points"]],
            "change": strength["change"],
        },
        weekly_training=[{**week, "week_start": week["week_start"].isoformat()}
                         for week in weekly_training(workouts, today, since)],
    )
