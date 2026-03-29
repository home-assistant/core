"""Fixtures for ccl integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.ccl.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

WEBHOOK_ID = "c2507426"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="CCL Weather Station",
        domain=DOMAIN,
        data={
            CONF_WEBHOOK_ID: WEBHOOK_ID,
            CONF_HOST: "192.168.1.185",
            CONF_PORT: "8123",
        },
        unique_id="0000-0000",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.ccl.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_ccl() -> Generator[MagicMock]:
    """Return a mocked CCL device."""
    with patch("aioccl.CCLDevice", autospec=True) as device_mock:
        device_mock = device_mock.return_value

        device_mock.info = {
            "fw_ver": "1.0.0",
            "last_update_time": None,
            "mac_address": "48:31:B7:06:D5:59",
            "model": "HA100",
            "passkey": WEBHOOK_ID,
            "serial_no": "12345",
        }
        device_mock.sensors = {}

        yield device_mock


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ccl: MagicMock,
) -> MockConfigEntry:
    """Set up the ccl integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
