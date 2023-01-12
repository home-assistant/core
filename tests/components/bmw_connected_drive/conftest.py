"""Fixtures for BMW tests."""

from bimmer_connected.api.authentication import MyBMWAuthentication
import pytest

from . import mock_login, mock_vehicles


@pytest.fixture
async def bmw_fixture(monkeypatch):
    """Patch the MyBMW Login and mock HTTP calls."""
    monkeypatch.setattr(MyBMWAuthentication, "login", mock_login)

    with mock_vehicles():
        yield mock_vehicles
