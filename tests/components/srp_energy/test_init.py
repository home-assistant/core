"""Tests for Srp Energy component Init."""
from homeassistant.components import srp_energy

from tests.components.srp_energy import init_integration


async def test_setup(hass):
    """Test for successfully setting up the platform."""
    config_entry = await init_integration(hass)
    assert srp_energy.DOMAIN in hass.config.components
    assert config_entry.entry_id in hass.data[srp_energy.DOMAIN]


async def test_unload_entry(hass):
    """Test being able to unload an entry."""
    config_entry = await init_integration(hass)
    assert hass.data[srp_energy.DOMAIN]

    assert await srp_energy.async_unload_entry(hass, config_entry)
    assert not hass.data[srp_energy.DOMAIN]


async def test_async_setup_entry_with_exception(hass):
    """Test exception when SrpClient can't load."""
    await init_integration(hass, side_effect=Exception())
    assert hass.data[srp_energy.DOMAIN] == {}
