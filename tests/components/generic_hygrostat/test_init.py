"""Test generic_hygrostat component."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENT_SENSOR = "sensor.test"
ENT_SWITCH = "switch.test"


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
