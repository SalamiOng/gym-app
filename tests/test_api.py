"""The read-only JSON API under /api."""

import urllib.error

import pytest

from conftest import TODAY, days_ago


def test_barcode_found(client, fake_off):
    fake_off.response = {"status": 1, "product": {"product_name": "Skyr", "serving_size": "150 g", "nutriments": {
        "energy-kcal_serving": 95, "proteins_serving": 16.5, "carbohydrates_serving": 6, "fat_serving": 0.3}}}
    response = client.get("/api/barcode/3017620422003")
    assert response.status_code == 200
    assert response.get_json() == {"product": {
        "barcode": "3017620422003", "name": "Skyr", "serving": "150 g", "per_serving": True,
        "calories": 95, "protein_g": 16.5, "carbs_g": 6, "fat_g": 0.3, "missing": [],
    }}


@pytest.mark.parametrize("code, response, status", [
    ("123", None, 400),
    ("3017620422003", {"status": 0}, 404),
    ("3017620422003", urllib.error.URLError("offline"), 503),
])
def test_barcode_errors(client, fake_off, code, response, status):
    fake_off.response = response
    result = client.get(f"/api/barcode/{code}")
    assert result.status_code == status
    assert result.is_json and result.get_json()["error"]


def test_nutrition_for_a_day(client):
    for name, calories, day in [("Oats", "300", TODAY.isoformat()), ("Egg", "70.5", TODAY.isoformat()), ("Old", "999", days_ago(1))]:
        client.post("/nutrition", data={"name": name, "serving": "1", "meal": "breakfast", "calories": calories,
                                        "protein_g": "10", "carbs_g": "5", "fat_g": "2", "eaten_on": day})
    client.post("/nutrition/goals", data={"calories": "2000"})

    data = client.get("/api/nutrition").get_json()
    assert data["date"] == TODAY.isoformat()
    assert [f["name"] for f in data["foods"]] == ["Oats", "Egg"]
    assert data["totals"] == {"calories": 370.5, "protein_g": 20, "carbs_g": 10, "fat_g": 4}
    assert data["goals"] == {"calories": 2000, "protein_g": None, "carbs_g": None, "fat_g": None}

    assert [f["name"] for f in client.get(f"/api/nutrition?date={days_ago(1)}").get_json()["foods"]] == ["Old"]


@pytest.mark.parametrize("query, message", [("banana", "YYYY-MM-DD"), ("2999-01-01", "future")])
def test_nutrition_bad_dates(client, query, message):
    response = client.get(f"/api/nutrition?date={query}")
    assert response.status_code == 400
    assert message in response.get_json()["error"]


def test_progress_series(client):
    client.post("/workouts", data={"exercise": "Bench Press", "sets": 3, "reps": 5, "weight": 40, "performed_on": days_ago(100)})
    client.post("/workouts", data={"exercise": "Bench Press", "sets": 3, "reps": 5, "weight": 50, "performed_on": days_ago(10)})
    client.post("/workouts", data={"exercise": "Bench Press", "sets": 3, "reps": 5, "weight": 55, "performed_on": days_ago(3)})
    client.post("/progress", data={"weight_lb": "180", "measured_on": days_ago(60)})

    data = client.get("/api/progress").get_json()
    assert data["range"] == "all" and data["since"] is None
    assert [p["value"] for p in data["strength"]["points"]] == [40, 50, 55]
    assert data["body_weight"] == [{"date": days_ago(60), "weight_lb": 180}]

    data = client.get("/api/progress?range=1m&exercise=bench+press&metric=volume").get_json()
    assert data["strength"]["metric"] == "volume"
    assert [p["value"] for p in data["strength"]["points"]] == [750, 825]
    assert data["strength"]["change"] == 75
    assert data["body_weight"] == []
    assert sum(week["days"] for week in data["weekly_training"]) == 2


def test_progress_with_no_data(client):
    assert client.get("/api/progress").get_json() == {
        "range": "all", "since": None, "body_weight": [], "strength": None, "weekly_training": []}


@pytest.mark.parametrize("query, status", [("?range=5y", 400), ("?exercise=Curl", 404)])
def test_progress_errors(client, query, status):
    response = client.get("/api/progress" + query)
    assert response.status_code == status
    assert "error" in response.get_json()


def test_unknown_api_routes_and_methods_answer_in_json(client):
    assert client.get("/api/nope").get_json() == {"error": "Not found."}
    response = client.post("/api/nutrition")
    assert response.status_code == 405
    assert response.get_json() == {"error": "Method not allowed."}
