"""Fixtures for Lytiva integration tests."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.lytiva.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Lytiva",
        data={},
        unique_id="lytiva_test",
    )


@pytest.fixture
async def setup_integration(hass: HomeAssistant, mqtt_mock, mock_config_entry: MockConfigEntry):
    """Set up the Lytiva integration with mocked MQTT."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
