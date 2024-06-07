"""Test fixtures for the Thread integration."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components import thread
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONFIG_ENTRY_DATA = {}


@pytest.fixture(name="thread_config_entry")
async def thread_config_entry_fixture(hass: HomeAssistant):
    """Mock Thread config entry."""
    config_entry = MockConfigEntry(
        data=CONFIG_ENTRY_DATA,
        domain=thread.DOMAIN,
        options={},
        title="Thread",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)


@pytest.fixture(autouse=True)
def use_mocked_zeroconf(mock_async_zeroconf: MagicMock) -> None:
    """Mock zeroconf in all tests."""
