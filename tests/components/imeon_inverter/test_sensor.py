"""Test the Imeon Inverter sensors."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.imeon_inverter.sensor import ENTITY_DESCRIPTIONS
from homeassistant.core import HomeAssistant


async def test_sensors_state(hass: HomeAssistant, snapshot: SnapshotAssertion) -> None:
    """Test the states of all sensors."""
    for sensor_key in [description.key for description in ENTITY_DESCRIPTIONS]:
        state = hass.states.get(f"sensor.imeon_inverter_{sensor_key}")
        assert state == snapshot
