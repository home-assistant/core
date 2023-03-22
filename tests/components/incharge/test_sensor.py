"""Test InCharge Sensor component."""
from homeassistant.core import HomeAssistant

from . import entry, setup_integration


async def test_incharge_sensor_class(hass: HomeAssistant) -> None:
    """Test incharge sensor class."""
    await setup_integration(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.station2_total_energy_consumption")
    assert state.state == "2000.0"
    state2 = hass.states.get("sensor.station1_total_energy_consumption")
    assert state2.state == "1000.0"

    await hass.config_entries.async_unload(entry.entry_id)
