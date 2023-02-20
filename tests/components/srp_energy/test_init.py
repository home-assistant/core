"""Tests for Srp Energy component Init."""
from homeassistant import config_entries
from homeassistant.components import srp_energy
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setup entry fails if deCONZ is not available."""
    config_entry = await init_integration(hass)
    assert config_entry.state == config_entries.ConfigEntryState.LOADED
    assert hass.data[srp_energy.SRP_ENERGY_DOMAIN]


async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test being able to unload an entry."""
    config_entry = await init_integration(hass)
    assert hass.data[srp_energy.SRP_ENERGY_DOMAIN]

    assert await srp_energy.async_unload_entry(hass, config_entry)
    assert not hass.data[srp_energy.SRP_ENERGY_DOMAIN]


async def test_async_setup_entry_with_exception(hass: HomeAssistant) -> None:
    """Test exception when SrpClient can't load."""
    await init_integration(hass, side_effect=Exception())
    assert srp_energy.SRP_ENERGY_DOMAIN not in hass.data
