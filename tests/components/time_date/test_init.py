"""The tests for the Time & Date component."""

from homeassistant.core import HomeAssistant

from . import load_int


async def test_setup_and_remove_config_entry(hass: HomeAssistant) -> None:
    """Test setting up and removing a config entry."""
    entry = await load_int(hass)

    state = hass.states.get("sensor.time")
    assert state is not None

    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.time") is None
