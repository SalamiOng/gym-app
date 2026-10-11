"""Shared pytest fixtures. Every test gets its own temporary database, so real data in instance/ is never touched,
and the network is blocked, so no test ever calls the real Open Food Facts API."""

import sqlite3
from contextlib import closing
from datetime import date, timedelta

import pytest

from gym_app import create_app, food_lookup

TODAY = date.today()


def days_ago(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(url, user_agent):
        raise AssertionError(f"Tests must not reach the network (tried {url}). Use the fake_off fixture.")

    monkeypatch.setattr(food_lookup, "_fetch_json", blocked)


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite3"), "SECRET_KEY": "test"})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def query(app):
    """Run SQL against the test database directly, to check what was really saved."""
    def run(sql: str, params: tuple = ()) -> list[tuple]:
        with closing(sqlite3.connect(app.config["DATABASE"])) as db:
            return db.execute(sql, params).fetchall()
    return run


@pytest.fixture
def fake_off(monkeypatch):
    """Replace the Open Food Facts call. Set `.response` to a dict to return, or an exception to raise."""
    class FakeOpenFoodFacts:
        response: object = {"status": 0}
        calls: list = []

        def __call__(self, url, user_agent):
            self.calls.append((url, user_agent))
            if isinstance(self.response, BaseException):
                raise self.response
            return self.response

    fake = FakeOpenFoodFacts()
    fake.calls = []
    monkeypatch.setattr(food_lookup, "_fetch_json", fake)
    return fake
