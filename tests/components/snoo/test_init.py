"""Test init for Snoo."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import async_init_integration
from .conftest import MockedSnoo


async def test_async_setup_entry(hass: HomeAssistant, bypass_api: MockedSnoo) -> None:
    """Test a successful setup entry."""
    entry = await async_init_integration(hass)
    assert len(hass.states.async_all("sensor")) == 2
    assert entry.state == ConfigEntryState.LOADED
