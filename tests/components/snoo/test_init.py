"""Test init for Snoo."""

from homeassistant.core import HomeAssistant

from . import async_init_integration


async def test_async_setup_entry(hass: HomeAssistant, bypass_api) -> None:
    """Test a successful setup entry."""
    await async_init_integration(hass)
