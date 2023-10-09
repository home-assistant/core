"""Tests for Google Tasks."""
from collections.abc import Awaitable, Callable

from homeassistant.components.google_tasks import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup(
    hass: HomeAssistant,
    integration_setup: Callable[[], Awaitable[bool]],
    config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """Test successful setup and unload."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    await integration_setup()
    assert config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.NOT_LOADED
    assert not hass.services.async_services().get(DOMAIN)
