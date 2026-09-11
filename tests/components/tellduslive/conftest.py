"""Common fixtures for the TelldusLive tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from tellduslive import TURNON

from homeassistant.components.tellduslive.const import (
    DOMAIN,
    KEY_SCAN_INTERVAL,
    KEY_SESSION,
)

from tests.common import MockConfigEntry

HUB_ID = "hub-1"
DEVICE_ID = "device-1"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock TelldusLive config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            KEY_SCAN_INTERVAL: 60,
            KEY_SESSION: {"token": "token", "token_secret": "token_secret"},
        },
    )


@pytest.fixture
def mock_tellduslive() -> Generator[MagicMock]:
    """Mock a TelldusLive session serving one hub and one switch."""
    device = MagicMock()
    device.device_id = DEVICE_ID
    device.name = "Kitchen"
    device.is_sensor = False
    device.methods = TURNON
    device.state = 0
    device.battery = None
    device.lastUpdated = None
    device.info.return_value = {
        "model": "selflearning-switch",
        "protocol": "arctech",
        "client": HUB_ID,
    }

    session = MagicMock()
    session.is_authorized = True
    session.get_clients.return_value = [
        {
            "id": HUB_ID,
            "name": "Mock hub",
            "type": "TellstickNet",
            "version": "17",
        }
    ]
    session.update.return_value = True
    session.device_ids = [DEVICE_ID]
    session.devices = [device]
    session.device.return_value = device

    with patch("homeassistant.components.tellduslive.Session", return_value=session):
        yield session
