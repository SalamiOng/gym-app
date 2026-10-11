"""Look up packaged foods by barcode with the Open Food Facts API (free and open, no API key needed).

Docs: https://openfoodfacts.github.io/openfoodfacts-server/api/
Only `lookup_barcode` talks to the network; everything else is plain parsing so it can be tested offline.
"""

import json
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass

import certifi

from .forms import MAX_FOOD_NAME_LENGTH, MAX_SERVING_LENGTH

API_URL = "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
# Ask only for what we use, which keeps responses small.
FIELDS = "code,product_name,brands,serving_size,nutriments"
TIMEOUT_SECONDS = 6
KJ_PER_KCAL = 4.184

# EAN-8, UPC-A, EAN-13 and GTIN-14: the barcodes printed on food packaging.
VALID_LENGTHS = (8, 12, 13, 14)


class BarcodeLookupError(Exception):
    """Base class. `str(error)` is a message that can be shown to the user as is."""


class InvalidBarcode(BarcodeLookupError):
    pass


class ProductNotFound(BarcodeLookupError):
    pass


class LookupUnavailable(BarcodeLookupError):
    """Open Food Facts couldn't be reached, timed out or sent something we couldn't read."""


@dataclass
class Product:
    barcode: str
    name: str
    serving: str
    # None when Open Food Facts doesn't know the value; the user fills it in.
    calories: float | None
    protein_g: float | None
    carbs_g: float | None
    fat_g: float | None
    per_serving: bool  # False: values are per 100 g (or 100 ml)

    @property
    def missing(self) -> list[str]:
        return [key for key in ("calories", "protein_g", "carbs_g", "fat_g") if getattr(self, key) is None]

    def to_dict(self) -> dict:
        return {**asdict(self), "missing": self.missing}


def _check_digit_ok(code: str) -> bool:
    """GS1 check digit: from the right (excluding the check digit), weight digits 3, 1, 3, 1, ..."""
    body, check = code[:-1], int(code[-1])
    total = sum(int(digit) * (3 if i % 2 == 0 else 1) for i, digit in enumerate(reversed(body)))
    return (10 - total % 10) % 10 == check


def normalize_barcode(raw: str) -> str:
    """Strip spaces and dashes, then check it looks like a real product barcode. Raises InvalidBarcode."""
    code = "".join(raw.split()).replace("-", "")
    if not code:
        raise InvalidBarcode("Enter a barcode.")
    if not code.isascii() or not code.isdigit():
        raise InvalidBarcode("A barcode is digits only, e.g. 3017620422003.")
    if len(code) not in VALID_LENGTHS:
        raise InvalidBarcode("A barcode has 8, 12, 13 or 14 digits.")
    if _check_digit_ok(code):
        return code
    if len(code) == 8 and code[0] in "01" and _check_digit_ok(_expand_upc_e(code)):
        return _expand_upc_e(code)
    raise InvalidBarcode("That barcode doesn't look right. Check the digits and try again.")


def _expand_upc_e(code: str) -> str:
    """Short 8-digit UPC-E codes (small US packs) to the full 12-digit UPC-A they abbreviate."""
    system, d, check = code[0], code[1:7], code[7]
    if d[5] in "012":
        body = d[0:2] + d[5] + "0000" + d[2:5]
    elif d[5] == "3":
        body = d[0:3] + "00000" + d[3:5]
    elif d[5] == "4":
        body = d[0:4] + "00000" + d[4]
    else:
        body = d[0:5] + "0000" + d[5]
    return system + body + check


def _number(nutriments: dict, key: str) -> float | None:
    value = nutriments.get(key)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, 1) if number >= 0 else None  # also drops nan


def _nutrients(nutriments: dict, suffix: str) -> dict[str, float | None]:
    calories = _number(nutriments, f"energy-kcal{suffix}")
    if calories is None:
        # Some products only list energy in kJ.
        kilojoules = _number(nutriments, f"energy-kj{suffix}")
        if kilojoules is None:
            kilojoules = _number(nutriments, f"energy{suffix}")  # plain "energy" is always kJ
        calories = round(kilojoules / KJ_PER_KCAL, 1) if kilojoules is not None else None
    return {
        "calories": calories,
        "protein_g": _number(nutriments, f"proteins{suffix}"),
        "carbs_g": _number(nutriments, f"carbohydrates{suffix}"),
        "fat_g": _number(nutriments, f"fat{suffix}"),
    }


def _not_found_message(barcode: str) -> str:
    return f"No product found for barcode {barcode}. You can enter it manually below."


def parse_product(barcode: str, payload: dict) -> Product:
    """Turn an Open Food Facts response into a Product. Raises ProductNotFound if it has no product."""
    product = payload.get("product")
    if payload.get("status") != 1 or not isinstance(product, dict):
        raise ProductNotFound(_not_found_message(barcode))

    name = " ".join(str(product.get("product_name") or "").split())
    brand = " ".join(str(product.get("brands") or "").split(",")[0].split())
    if name and brand and brand.casefold() not in name.casefold():
        name = f"{name} ({brand})"
    name = (name or brand or f"Product {barcode}")[:MAX_FOOD_NAME_LENGTH]

    nutriments = product.get("nutriments") if isinstance(product.get("nutriments"), dict) else {}
    serving_size = " ".join(str(product.get("serving_size") or "").split())[:MAX_SERVING_LENGTH]
    per_serving = _nutrients(nutriments, "_serving")
    # Prefer per-serving values when the label has them, since that's what people usually eat.
    if serving_size and per_serving["calories"] is not None:
        return Product(barcode, name, serving_size, per_serving=True, **per_serving)
    return Product(barcode, name, "100 g", per_serving=False, **_nutrients(nutriments, "_100g"))


def _fetch_json(url: str, user_agent: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    # certifi's CA bundle, because some Python installs (e.g. python.org on macOS) ship without one.
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS, context=context) as response:
        return json.load(response)


def lookup_barcode(raw: str, user_agent: str) -> Product:
    """Validate the barcode, fetch it from Open Food Facts and parse the result.

    Raises InvalidBarcode, ProductNotFound or LookupUnavailable, each with a user-facing message.
    """
    barcode = normalize_barcode(raw)
    url = API_URL.format(barcode=barcode) + "?" + urllib.parse.urlencode({"fields": FIELDS})
    unavailable = "Couldn't reach Open Food Facts right now. Try again, or enter the food manually."
    try:
        payload = _fetch_json(url, user_agent)
    except urllib.error.HTTPError as error:
        # The v2 API answers 404 for unknown barcodes.
        if error.code == 404:
            raise ProductNotFound(_not_found_message(barcode)) from error
        raise LookupUnavailable(unavailable) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, ValueError) as error:
        # ValueError covers a response that isn't valid JSON (JSONDecodeError and UnicodeDecodeError).
        raise LookupUnavailable(unavailable) from error
    if not isinstance(payload, dict):
        raise LookupUnavailable(unavailable)
    return parse_product(barcode, payload)
