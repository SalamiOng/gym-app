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


def strength_series(workouts: list[dict], key: str) -> dict:
    """Best set per day for one exercise: heaviest weight, or most reps if it's only ever done at 0 kg."""
    rows = [w for w in workouts if exercise_key(w["exercise"]) == key]
    by_weight = any(w["weight"] > 0 for w in rows)
    field, unit = ("weight", "kg") if by_weight else ("reps", "reps")

    best_per_day: dict[date, float] = {}
    for w in rows:
        best_per_day[w["performed_on"]] = max(best_per_day.get(w["performed_on"], 0), w[field])
    points = sorted(best_per_day.items())

    return {
        "points": points,
        "unit": unit,
        "metric": "Heaviest set per session" if by_weight else "Most reps in a set per session",
        # None with one session: nothing to compare against yet. Rounded to hide float noise.
        "change": round(points[-1][1] - points[0][1], 2) if len(points) > 1 else None,
        "since": points[0][0],
    }
