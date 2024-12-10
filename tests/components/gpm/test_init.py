"""Tests for the GPM init."""

from homeassistant.components.gpm._manager import IntegrationRepositoryManager
from homeassistant.components.gpm.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_async_remove_entry(
    hass: HomeAssistant, integration_manager: IntegrationRepositoryManager
) -> None:
    """Test async_remove_entry."""
    entry = await init_integration(hass)

    assert DOMAIN in hass.config.components

    await hass.config_entries.async_remove(entry.entry_id)
    integration_manager.remove.assert_awaited_once()
