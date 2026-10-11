"""Barcode lookup with Open Food Facts: barcode validation, response parsing, error handling and the Nutrition page.
The network is always faked (see conftest.fake_off)."""

import json
import socket
import urllib.error
from io import BytesIO

import pytest

from conftest import TODAY, days_ago
from gym_app.food_lookup import (
    InvalidBarcode,
    LookupUnavailable,
    ProductNotFound,
    lookup_barcode,
    normalize_barcode,
    parse_product,
)

NUTELLA = {
    "status": 1,
    "product": {
        "product_name": "Nutella",
        "brands": "Nutella, Ferrero",
        "nutriments": {"energy-kcal_100g": 539, "proteins_100g": 6.3, "carbohydrates_100g": 57.5, "fat_100g": 30.9},
    },
}
COLA = {
    "status": 1,
    "product": {
        "product_name": "Coca-Cola Original",
        "brands": "Coca-Cola",
        "serving_size": "1 can (330 ml)",
        "nutriments": {
            "energy-kcal_100g": 42, "energy-kcal_serving": 139, "proteins_serving": 0,
            "carbohydrates_serving": 35, "fat_serving": 0, "carbohydrates_100g": 10.6,
        },
    },
}


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://example", code, "error", {}, BytesIO(b""))


# --- Barcode validation


@pytest.mark.parametrize("raw, expected", [
    ("3017620422003", "3017620422003"),  # EAN-13
    (" 3017 6204-22003 ", "3017620422003"),  # spaces and dashes are ignored
    ("96385074", "96385074"),  # EAN-8
    ("036000291452", "036000291452"),  # UPC-A
    ("04252614", "042100005264"),  # UPC-E, expanded to UPC-A
    ("10012345678902", "10012345678902"),  # GTIN-14
])
def test_valid_barcodes(raw, expected):
    assert normalize_barcode(raw) == expected


@pytest.mark.parametrize("raw, message", [
    ("", "Enter a barcode."),
    ("30176204220a3", "digits only"),
    ("３０１７６２０４２２００３", "digits only"),  # full-width digits
    ("12345", "8, 12, 13 or 14 digits"),
    ("3017620422004", "doesn't look right"),  # wrong check digit
])
def test_invalid_barcodes(raw, message):
    with pytest.raises(InvalidBarcode, match=message):
        normalize_barcode(raw)


# --- Parsing Open Food Facts responses


def test_per_100g_when_there_is_no_serving_size():
    product = parse_product("3017620422003", NUTELLA)
    assert (product.name, product.serving, product.per_serving) == ("Nutella", "100 g", False)
    assert (product.calories, product.protein_g, product.carbs_g, product.fat_g) == (539, 6.3, 57.5, 30.9)
    assert product.missing == []


def test_per_serving_is_preferred_and_brand_is_added():
    product = parse_product("5449000000996", COLA)
    assert product.name == "Coca-Cola Original"  # brand already in the name, so not repeated
    assert (product.serving, product.per_serving, product.calories, product.carbs_g) == ("1 can (330 ml)", True, 139, 35)

    other_brand = {"status": 1, "product": {**COLA["product"], "product_name": "Cola", "brands": "Acme, Big Co"}}
    assert parse_product("5449000000996", other_brand).name == "Cola (Acme)"


def test_kilojoules_are_converted_when_kcal_is_missing():
    payload = {"status": 1, "product": {"product_name": "Oats", "nutriments": {"energy-kj_100g": 1556, "fat_100g": "7"}}}
    product = parse_product("3017620422003", payload)
    assert product.calories == 371.9
    assert product.fat_g == 7  # numbers sent as strings are accepted
    assert product.missing == ["protein_g", "carbs_g"]


def test_missing_or_bad_nutrition_values_are_left_blank():
    payload = {"status": 1, "product": {"brands": "Acme", "nutriments": {"proteins_100g": "n/a", "fat_100g": -3}}}
    product = parse_product("3017620422003", payload)
    assert product.name == "Acme"
    assert product.missing == ["calories", "protein_g", "carbs_g", "fat_g"]


def test_long_names_are_cut_to_fit_the_form():
    payload = {"status": 1, "product": {"product_name": "x" * 300, "serving_size": "y" * 80, "nutriments": {}}}
    product = parse_product("3017620422003", payload)
    assert len(product.name) == 100


def test_product_with_no_name_gets_a_placeholder():
    assert parse_product("3017620422003", {"status": 1, "product": {}}).name == "Product 3017620422003"


@pytest.mark.parametrize("payload", [{"status": 0, "status_verbose": "product not found"}, {"status": 1}, {}])
def test_responses_without_a_product_mean_not_found(payload):
    with pytest.raises(ProductNotFound, match="No product found for barcode 3017620422003"):
        parse_product("3017620422003", payload)


# --- lookup_barcode: network handling


def test_lookup_calls_the_v2_api_with_a_user_agent(fake_off):
    fake_off.response = NUTELLA
    assert lookup_barcode("3017620422003", "GymApp/test").name == "Nutella"
    [(url, user_agent)] = fake_off.calls
    assert url.startswith("https://world.openfoodfacts.org/api/v2/product/3017620422003.json?fields=")
    assert user_agent == "GymApp/test"


def test_invalid_barcode_never_reaches_the_network(fake_off):
    with pytest.raises(InvalidBarcode):
        lookup_barcode("123", "GymApp/test")
    assert fake_off.calls == []


@pytest.mark.parametrize("failure, expected", [
    (http_error(404), ProductNotFound),
    (http_error(500), LookupUnavailable),
    (http_error(429), LookupUnavailable),
    (urllib.error.URLError("no route to host"), LookupUnavailable),
    (socket.timeout("timed out"), LookupUnavailable),
    (TimeoutError(), LookupUnavailable),
    (ConnectionResetError(), LookupUnavailable),
    (json.JSONDecodeError("bad", "<html>", 0), LookupUnavailable),
])
def test_network_failures_become_friendly_errors(fake_off, failure, expected):
    fake_off.response = failure
    with pytest.raises(expected) as info:
        lookup_barcode("3017620422003", "GymApp/test")
    assert "Open Food Facts" in str(info.value) or "No product found" in str(info.value)


def test_non_object_json_is_unavailable(fake_off):
    fake_off.response = ["not", "an", "object"]
    with pytest.raises(LookupUnavailable):
        lookup_barcode("3017620422003", "GymApp/test")


# --- Nutrition page


def test_lookup_prefills_the_food_form(client, fake_off, query):
    fake_off.response = COLA
    response = client.get("/nutrition?barcode=5449000000996")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Found <strong>Coca-Cola Original</strong>" in html
    assert "per serving" in html
    for field, value in [("name", "Coca-Cola Original"), ("serving", "1 can (330 ml)"), ("calories", "139"),
                         ("carbs_g", "35"), ("barcode", "5449000000996")]:
        assert f'name="{field}"' in html and f'value="{value}"' in html
    assert query("SELECT COUNT(*) FROM foods") == [(0,)]  # nothing is saved until the user adds it

    client.post("/nutrition", data={"name": "Coca-Cola Original", "serving": "1 can (330 ml)", "meal": "lunch",
                                    "calories": "139", "protein_g": "0", "carbs_g": "35", "fat_g": "0",
                                    "eaten_on": TODAY.isoformat()})
    assert query("SELECT name, calories FROM foods") == [("Coca-Cola Original", 139.0)]


def test_missing_values_are_flagged(client, fake_off):
    fake_off.response = {"status": 1, "product": {"product_name": "Mystery bar", "nutriments": {"energy-kcal_100g": 400}}}
    html = client.get("/nutrition?barcode=3017620422003").get_data(as_text=True)
    assert "Some nutrition values are missing" in html
    assert 'name="protein_g" type="number" value=""' in html


def test_lookup_keeps_the_day_being_viewed(client, fake_off):
    fake_off.response = NUTELLA
    html = client.get(f"/nutrition?date={days_ago(3)}&barcode=3017620422003").get_data(as_text=True)
    assert f'<input type="hidden" name="date" value="{days_ago(3)}" />' in html
    assert f'name="eaten_on" type="date" value="{days_ago(3)}"' in html


@pytest.mark.parametrize("response, message", [
    ({"status": 0}, "No product found for barcode 3017620422003. You can enter it manually below."),
    (urllib.error.URLError("offline"), "Couldn&#39;t reach Open Food Facts right now."),
])
def test_lookup_errors_are_shown_and_manual_entry_still_works(client, fake_off, response, message):
    fake_off.response = response
    response = client.get("/nutrition?barcode=3017620422003")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert message in html
    assert 'role="alert"' in html
    assert 'name="name" type="text" value=""' in html  # empty form, ready to fill in by hand


def test_invalid_barcode_on_the_page(client, fake_off):
    html = client.get("/nutrition?barcode=<b>12</b>").get_data(as_text=True)
    assert "A barcode is digits only" in html
    assert "<b>12</b>" not in html  # echoed back escaped
    assert fake_off.calls == []


def test_scanner_is_progressive_enhancement(client):
    html = client.get("/nutrition").get_data(as_text=True)
    assert "data-scan-start hidden" in html  # only shown by JS when a camera can be used
    assert "js/barcode.js" in html
    assert 'id="barcode"' in html  # typing a barcode always works


def test_user_agent_comes_from_config(tmp_path, fake_off):
    from gym_app import create_app

    fake_off.response = NUTELLA
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "db.sqlite3"), "OPENFOODFACTS_USER_AGENT": "Custom/2.0"})
    app.test_client().get("/nutrition?barcode=3017620422003")
    assert fake_off.calls[0][1] == "Custom/2.0"
