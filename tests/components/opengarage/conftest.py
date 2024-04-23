"""Fixtures for the OpenGarage integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.opengarage.const import CONF_DEVICE_KEY, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Test device",
        domain=DOMAIN,
        data={
            CONF_HOST: "http://1.1.1.1",
            CONF_PORT: "80",
            CONF_DEVICE_KEY: "abc123",
            CONF_VERIFY_SSL: False,
        },
        unique_id="12345",
    )


@pytest.fixture
def mock_opengarage() -> Generator[MagicMock, None, None]:
    """Return a mocked OpenGarage client."""
    with patch(
        "homeassistant.components.opengarage.opengarage.OpenGarage",
        autospec=True,
    ) as client_mock:
        client = client_mock.return_value
        client.device_url = "http://1.1.1.1:80"
        client.update_state.return_value = {
            "name": "abcdef",
            "mac": "aa:bb:cc:dd:ee:ff",
            "fwv": "1.2.0",
        }
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_opengarage: MagicMock
) -> MockConfigEntry:
    """Set up the OpenGarage integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
