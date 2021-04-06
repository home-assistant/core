"""Test the Met integration init."""
from homeassistant.components.met.const import (
    DEFAULT_HOME_LATITUDE,
    DEFAULT_HOME_LONGITUDE,
    DOMAIN,
)
from homeassistant.config import async_process_ha_core_config
from homeassistant.config_entries import (
    ENTRY_STATE_LOADED,
    ENTRY_STATE_NOT_LOADED,
    ENTRY_STATE_SETUP_ERROR,
)

from . import init_integration


async def test_unload_entry(hass):
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state == ENTRY_STATE_NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_fail_default_home_entry(hass, caplog):
    """Test abort setup of default home location."""
    await async_process_ha_core_config(
        hass,
        {"latitude": 52.3731339, "longitude": 4.8903147},
    )

    assert hass.config.latitude == DEFAULT_HOME_LATITUDE
    assert hass.config.longitude == DEFAULT_HOME_LONGITUDE

    entry = await init_integration(hass, track_home=True)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state == ENTRY_STATE_SETUP_ERROR

    assert (
        "Skip setting up met.no integration; No Home location has been set"
        in caplog.text
    )
