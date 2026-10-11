"""Workout statistics for the Progress page, computed from `list_workouts()` rows (newest first)."""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class ExerciseSummary:
    key: str
    name: str  # spelling from the most recent entry
    sessions: int  # distinct days trained
    best_weight: float
    best_reps: int  # reps done at best_weight
    best_1rm: float
    last_on: date


def exercise_key(name: str) -> str:
    """Exercise names are free text, so "bench press" and "Bench  Press" count as one exercise."""
    return " ".join(name.split()).casefold()


def estimated_1rm(weight: float, reps: int) -> float:
    """Epley formula. Only an estimate, and less reliable above ~10 reps."""
    return weight if reps == 1 else weight * (1 + reps / 30)


def exercise_summaries(workouts: list[dict]) -> list[ExerciseSummary]:
    """One summary per exercise, most recently trained first."""
    groups: dict[str, list[dict]] = {}
    for workout in workouts:  # newest first, so each group's first row is its latest
        groups.setdefault(exercise_key(workout["exercise"]), []).append(workout)

    summaries = []
    for key, rows in groups.items():
        best = max(rows, key=lambda w: (w["weight"], w["reps"]))
        summaries.append(ExerciseSummary(
            key=key,
            name=rows[0]["exercise"],
            sessions=len({w["performed_on"] for w in rows}),
            best_weight=best["weight"],
            best_reps=best["reps"],
            best_1rm=round(max(estimated_1rm(w["weight"], w["reps"]) for w in rows), 1),
            last_on=rows[0]["performed_on"],
        ))
    return summaries


def find_exercise(summaries: list[ExerciseSummary], name: str) -> ExerciseSummary | None:
    key = exercise_key(name)
    return next((s for s in summaries if s.key == key), None)


def workout_stats(workouts: list[dict], summaries: list[ExerciseSummary], today: date) -> dict | None:
    if not workouts:
        return None
    days = {w["performed_on"] for w in workouts}
    week_start = today - timedelta(days=today.weekday())  # Monday
    return {
        "training_days": len(days),
        "days_this_week": sum(week_start <= d <= today for d in days),
        "entries": len(workouts),
        "sets": sum(w["sets"] for w in workouts),
        # Total weight moved: sets × reps × weight. Bodyweight entries (0 kg) add nothing.
        "volume": round(sum(w["sets"] * w["reps"] * w["weight"] for w in workouts)),
        # Ties go to the most recently trained exercise.
        "most_trained": max(summaries, key=lambda s: s.sessions),
    }


# Chart date ranges for the Progress page: ?range=<key> -> (button label, days back; None = everything).
RANGES = {"1m": ("1M", 30), "3m": ("3M", 91), "1y": ("1Y", 365), "all": ("All", None)}
RANGE_DESCRIPTIONS = {"1m": "the last month", "3m": "the last 3 months", "1y": "the last year", "all": "all time"}
DEFAULT_RANGE = "all"

# Strength chart metrics: ?metric=<key> -> label. Bodyweight-only exercises use reps instead of kg.
METRICS = {
    "best": ("Heaviest set per session", "Most reps in a set per session"),
    "e1rm": ("Best estimated 1RM per session", None),  # needs weight, so not offered for bodyweight moves
    "volume": ("Volume per session (sets × reps × weight)", "Total reps per session"),
}
MAX_WEEKS = 52


def range_start(range_key: str, today: date) -> date | None:
    """First day included in a chart range, or None for all time. Unknown keys mean all time."""
    days = RANGES.get(range_key, RANGES[DEFAULT_RANGE])[1]
    return None if days is None else today - timedelta(days=days - 1)


def strength_series(workouts: list[dict], key: str, metric: str = "best", since: date | None = None) -> dict:
    """One value per session (day) for one exercise, oldest first.

    "best": heaviest set, or most reps if it's only ever done at 0 kg. "e1rm": best estimated 1RM.
    "volume": sets × reps × weight added up (total reps for bodyweight moves). Unknown metrics mean "best".
    `since` drops sessions before that day.
    """
    rows = [w for w in workouts if exercise_key(w["exercise"]) == key]
    # Decided on every session, not just those in range, so the unit doesn't flip when the range changes.
    by_weight = any(w["weight"] > 0 for w in rows)
    available = [k for k, labels in METRICS.items() if labels[0 if by_weight else 1]]
    if metric not in available:
        metric = "best"

    def value(w: dict) -> float:
        if metric == "e1rm":
            return estimated_1rm(w["weight"], w["reps"])
        if metric == "volume":
            return w["sets"] * w["reps"] * (w["weight"] if by_weight else 1)
        return w["weight"] if by_weight else w["reps"]

    per_day: dict[date, float] = {}
    for w in rows:
        if since and w["performed_on"] < since:
            continue
        day = w["performed_on"]
        if metric == "volume":
            per_day[day] = per_day.get(day, 0) + value(w)
        else:
            per_day[day] = max(per_day.get(day, 0), value(w))
    points = sorted((day, round(v, 1)) for day, v in per_day.items())

    return {
        "points": points,
        "unit": "kg" if by_weight else "reps",
        "metric": METRICS[metric][0 if by_weight else 1],
        "metric_key": metric,
        "metrics": [(k, METRICS[k][0 if by_weight else 1]) for k in available],
        # None with fewer than two sessions: nothing to compare against yet. Rounded to hide float noise.
        "change": round(points[-1][1] - points[0][1], 2) if len(points) > 1 else None,
        "since": points[0][0] if points else None,
    }


def weekly_training(workouts: list[dict], today: date, since: date | None) -> list[dict]:
    """Training days and sets for each week (Monday to Sunday), oldest first, including empty weeks.

    Starts at the week containing `since` (or the first workout for all time), and covers at most MAX_WEEKS.
    """
    if not workouts:
        return []
    this_week = today - timedelta(days=today.weekday())
    first_day = since or min(w["performed_on"] for w in workouts)
    first_week = max(first_day - timedelta(days=first_day.weekday()), this_week - timedelta(weeks=MAX_WEEKS - 1))

    weeks = {first_week + timedelta(weeks=i): {"days": set(), "sets": 0}
             for i in range((this_week - first_week).days // 7 + 1)}
    for w in workouts:
        week = w["performed_on"] - timedelta(days=w["performed_on"].weekday())
        if week in weeks:
            weeks[week]["days"].add(w["performed_on"])
            weeks[week]["sets"] += w["sets"]
    return [{"week_start": week, "days": len(data["days"]), "sets": data["sets"]} for week, data in sorted(weeks.items())]
