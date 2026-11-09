"""Common fixtures for the TelldusLive tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.tellduslive.const import (
    CLOUD_NAME,
    DOMAIN,
    KEY_REQUEST_DELAY,
    KEY_SCAN_INTERVAL,
    KEY_SESSION,
    TURNON,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

HUB_ID = "hub-1"
DEVICE_ID = "device-1"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock TelldusLive config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: CLOUD_NAME,
            KEY_SCAN_INTERVAL: 60,
            KEY_SESSION: {"token": "token", "token_secret": "token_secret"},
        },
        options={KEY_REQUEST_DELAY: 0},
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
    session.update.return_value = None
    session.dump_state.return_value = {}
    session.ok_responses_last_hour.return_value = 0
    session.device_ids = [DEVICE_ID]
    session.devices = [device]
    session.device.return_value = device

    with patch("homeassistant.components.tellduslive.Session", return_value=session):
        yield session


@pytest.fixture
def device(mock_tellduslive: MagicMock) -> MagicMock:
    """Return the mocked device served by the mocked session."""
    return mock_tellduslive.devices[0]


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tellduslive: MagicMock,
    device: MagicMock,
) -> MockConfigEntry:
    """Set up the integration and wait for the first refresh."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await mock_config_entry.runtime_data.setup_task
    await hass.async_block_till_done()
    return mock_config_entry
