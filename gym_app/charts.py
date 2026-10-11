"""Line- and bar-chart geometry for the Progress page.

This module only does the maths; `line_chart` and `bar_chart` in partials/macros.html draw the result.
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


@dataclass(frozen=True)
class Bar:
    x: float  # centre
    width: float
    y: float  # top of the bar
    label: str  # tooltip


@dataclass(frozen=True)
class BarChart:
    bars: list[Bar]
    y_ticks: list[Tick]
    x_labels: list[str]  # first and last bar
    baseline: float  # y of 0, where bars start


def _short_date(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def _nice_step(raw: float) -> float:
    """Round a tick spacing up to 1, 2, 2.5 or 5 times a power of ten."""
    magnitude = 10 ** math.floor(math.log10(raw))
    for multiple in (1, 2, 2.5, 5, 10):
        if multiple * magnitude >= raw * (1 - 1e-9):
            return multiple * magnitude
    return 10 * magnitude  # unreachable; keeps type checkers happy


def _y_axis(values: list[float]):
    """A rounded axis covering every value. Returns (y(value) -> % from the top, ticks)."""
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

    tick_count = round((axis_high - axis_low) / step)
    tick_values = [round(axis_low + i * step, 6) for i in range(tick_count + 1)]
    return y, [Tick(y(value), f"{value:g}") for value in tick_values]


def line_chart(series: list[tuple[date, float]], unit: str) -> Chart | None:
    """Lay out (date, value) pairs on a time axis. Returns None when there is nothing to plot."""
    if not series:
        return None
    series = sorted(series)
    y, y_ticks = _y_axis([value for _, value in series])

    first_day, last_day = series[0][0], series[-1][0]
    day_span = (last_day - first_day).days

    def x(day: date) -> float:
        if day_span == 0:
            return 50
        share = (day - first_day).days / day_span
        return round(_X_LEFT + share * (_X_RIGHT - _X_LEFT), 3)

    return Chart(
        points=[Point(x(day), y(value), f"{_short_date(day)}: {value:g} {unit}") for day, value in series],
        y_ticks=y_ticks,
        x_labels=[_short_date(first_day)] if day_span == 0 else [_short_date(first_day), _short_date(last_day)],
    )


def bar_chart(bars: list[tuple[str, float, str]]) -> BarChart | None:
    """Evenly spaced bars from (axis label, value, tooltip) tuples, in order. None when there are no bars.
    Values must be 0 or more; the axis always starts at 0."""
    if not bars:
        return None
    y, y_ticks = _y_axis([0, *(value for _, value, _ in bars)])
    slot = 100 / len(bars)
    width = round(slot * 0.7, 3)  # a gap of 30% between bars
    return BarChart(
        bars=[Bar(round(slot * (i + 0.5), 3), width, y(value), tip) for i, (_, value, tip) in enumerate(bars)],
        y_ticks=y_ticks,
        x_labels=[bars[0][0]] if len(bars) == 1 else [bars[0][0], bars[-1][0]],
        baseline=y(0),
    )
