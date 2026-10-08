"""Line-chart geometry for the Progress page.

This module only does the maths; `line_chart` in partials/macros.html draws the result.
Coordinates are percentages of the plot area (0–100, y pointing down like SVG), so the
chart stretches to any width while its HTML labels keep a readable font size.
"""

import math
from dataclasses import dataclass
from datetime import date

# Keep points slightly inside the plot so dots on the edges aren't clipped.
_X_LEFT, _X_RIGHT = 3, 97
_Y_TOP, _Y_BOTTOM = 6, 94
_TARGET_TICKS = 4


@dataclass(frozen=True)
class Point:
    x: float
    y: float
    label: str  # shown as a tooltip on hover


@dataclass(frozen=True)
class Tick:
    y: float
    label: str


@dataclass(frozen=True)
class Chart:
    points: list[Point]
    y_ticks: list[Tick]
    x_labels: list[str]  # first and last date (just one if every point is on the same date)

    @property
    def polyline(self) -> str:
        return " ".join(f"{p.x},{p.y}" for p in self.points)


def _short_date(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def _nice_step(raw: float) -> float:
    """Round a tick spacing up to 1, 2, 2.5 or 5 times a power of ten."""
    magnitude = 10 ** math.floor(math.log10(raw))
    for multiple in (1, 2, 2.5, 5, 10):
        if multiple * magnitude >= raw * (1 - 1e-9):
            return multiple * magnitude
    return 10 * magnitude  # unreachable; keeps type checkers happy


def line_chart(series: list[tuple[date, float]], unit: str) -> Chart | None:
    """Lay out (date, value) pairs on a time axis. Returns None when there is nothing to plot."""
    if not series:
        return None
    series = sorted(series)
    values = [value for _, value in series]

    low, high = min(values), max(values)
    if low == high:
        # A flat line still needs a range; centre it.
        low, high = low - 1, high + 1
    if min(values) >= 0:
        low = max(low, 0)  # never show negative kg/lb/reps
    step = _nice_step((high - low) / _TARGET_TICKS)
    axis_low = math.floor(low / step) * step
    axis_high = math.ceil(high / step) * step

    def y(value: float) -> float:
        share = (value - axis_low) / (axis_high - axis_low)
        return round(_Y_BOTTOM - share * (_Y_BOTTOM - _Y_TOP), 3)

    first_day, last_day = series[0][0], series[-1][0]
    day_span = (last_day - first_day).days

    def x(day: date) -> float:
        if day_span == 0:
            return 50
        share = (day - first_day).days / day_span
        return round(_X_LEFT + share * (_X_RIGHT - _X_LEFT), 3)

    tick_count = round((axis_high - axis_low) / step)
    tick_values = [round(axis_low + i * step, 6) for i in range(tick_count + 1)]

    return Chart(
        points=[Point(x(day), y(value), f"{_short_date(day)}: {value:g} {unit}") for day, value in series],
        y_ticks=[Tick(y(value), f"{value:g}") for value in tick_values],
        x_labels=[_short_date(first_day)] if day_span == 0 else [_short_date(first_day), _short_date(last_day)],
    )
