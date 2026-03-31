"""Common fixtures for PAJ GPS integration tests."""

from __future__ import annotations

from collections.abc import Generator
import json
from unittest.mock import AsyncMock, patch

from pajgps_api.models.auth import AuthResponse
from pajgps_api.models.device import Device
from pajgps_api.models.trackpoint import TrackPoint
import pytest

from homeassistant.components.paj_gps.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry for PAJ GPS."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="test@example.com",
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "secret",
        },
    )


@pytest.fixture
def mock_paj_gps_api() -> Generator[AsyncMock]:
    """Mock PajGpsApi for PAJ GPS integration tests."""
    with (
        patch(
            "homeassistant.components.paj_gps.coordinator.PajGpsApi",
            autospec=True,
        ) as mock_api_cls,
        patch(
            "homeassistant.components.paj_gps.config_flow.PajGpsApi",
            new=mock_api_cls,
        ),
    ):
        api = mock_api_cls.return_value
        device_data = json.loads(load_fixture("device.json", DOMAIN))
        trackpoint_data = json.loads(load_fixture("trackpoint.json", DOMAIN))
        api.login.return_value = AuthResponse(
            userID=42, token="test_token", refresh_token="test_refresh"
        )
        api.get_devices.return_value = [Device(**device_data)]
        api.get_all_last_positions.return_value = [TrackPoint(**trackpoint_data)]
        yield api
