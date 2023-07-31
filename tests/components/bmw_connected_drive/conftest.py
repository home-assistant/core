"""Fixtures for BMW tests."""

from unittest.mock import AsyncMock, Mock

from bimmer_connected.api.authentication import MyBMWAuthentication
from bimmer_connected.vehicle.remote_services import RemoteServices, RemoteServiceStatus
import pytest

from homeassistant.components.bmw_connected_drive.coordinator import (
    BMWDataUpdateCoordinator,
)

from . import mock_login, mock_vehicles


@pytest.fixture
async def bmw_fixture(monkeypatch):
    """Patch the MyBMW Login and mock HTTP calls."""
    monkeypatch.setattr(MyBMWAuthentication, "login", mock_login)

    monkeypatch.setattr(
        RemoteServices,
        "trigger_remote_service",
        AsyncMock(return_value=RemoteServiceStatus({"eventStatus": "EXECUTED"})),
    )

    monkeypatch.setattr(
        BMWDataUpdateCoordinator,
        "async_update_listeners",
        Mock(),
    )

    with mock_vehicles():
        yield mock_vehicles
