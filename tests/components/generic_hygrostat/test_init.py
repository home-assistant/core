"""Test generic_hygrostat component."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, assert_setup_component

ENT_SENSOR = "sensor.test"
ENT_SWITCH = "switch.test"


async def test_setup_missing_conf(hass):
    """Test set up humidity_control with missing config values."""
    config = {
        "platform": "generic_hygrostat",
        "name": "test",
        "target_sensor": ENT_SENSOR,
    }
    with assert_setup_component(0):
        await async_setup_component(hass, "humidifier", {"humidifier": config})
        await hass.async_block_till_done()


async def test_valid_conf(hass):
    """Test set up generic_hygrostat with valid config values."""
    assert await async_setup_component(
        hass,
        "humidifier",
        {
            "humidifier": {
                "platform": "generic_hygrostat",
                "name": "test",
                "humidifier": ENT_SWITCH,
                "target_sensor": ENT_SENSOR,
            }
        },
    )
    await hass.async_block_till_done()


async def test_valid_config_entry(hass):
    """Test setting up a generic hygrostat with a valid config entry."""

    entry = MockConfigEntry(
        domain="generic_hygrostat",
        data={
            "name": "test",
            "humidifier": ENT_SWITCH,
            "target_sensor": ENT_SENSOR,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_async_unload_entry(hass: HomeAssistant) -> None:
    """Test pushbullet unload entry."""
    entry = MockConfigEntry(
        domain="generic_hygrostat",
        data={
            "name": "test",
            "humidifier": ENT_SWITCH,
            "target_sensor": ENT_SENSOR,
        },
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.NOT_LOADED
