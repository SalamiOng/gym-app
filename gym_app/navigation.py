from dataclasses import dataclass


@dataclass(frozen=True)
class NavItem:
    endpoint: str
    label: str
    icon: str


NAV_ITEMS = [
    NavItem("main.dashboard", "Dashboard", "layout-dashboard"),
    NavItem("main.workouts", "Workouts", "list-checks"),
    NavItem("main.exercises", "Exercises", "dumbbell"),
    NavItem("main.progress", "Progress", "line-chart"),
    NavItem("main.profile", "Profile", "user"),
]
