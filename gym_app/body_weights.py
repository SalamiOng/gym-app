from datetime import date

from .db import get_db
from .forms import BodyWeightEntry


def add_body_weight(entry: BodyWeightEntry) -> None:
    db = get_db()
    db.execute(
        "INSERT INTO body_weights (weight_lb, measured_on) VALUES (?, ?)",
        (entry.weight_lb, entry.measured_on.isoformat()),
    )
    db.commit()


def list_body_weights() -> list[dict]:
    """Newest date first; entries on the same date are newest-added first."""
    rows = get_db().execute(
        "SELECT id, weight_lb, measured_on FROM body_weights ORDER BY measured_on DESC, id DESC"
    ).fetchall()
    return [{**row, "measured_on": date.fromisoformat(row["measured_on"])} for row in rows]


def summarize(entries: list[dict]) -> dict | None:
    """Latest entry and change since the earliest. `entries` must be ordered as list_body_weights returns them."""
    if not entries:
        return None
    latest, earliest = entries[0], entries[-1]
    return {
        "latest": latest,
        "earliest": earliest,
        # None with a single entry: there's nothing to compare against yet.
        # Rounded so float noise (e.g. 2.2000000000000171) doesn't show up.
        "change": round(latest["weight_lb"] - earliest["weight_lb"], 2) if len(entries) > 1 else None,
    }
