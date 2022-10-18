"""Fixtures for BMW tests."""

from bimmer_connected.account import MyBMWAccount
import pytest

from . import mock_vehicles_from_fixture


@pytest.fixture
async def bmw_fixture(monkeypatch):
    """Patch the vehicle fixtures into a MyBMWAccount."""
    monkeypatch.setattr(MyBMWAccount, "get_vehicles", mock_vehicles_from_fixture)
