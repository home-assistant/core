"""Test the Whirlpool Sensor domain."""
from unittest.mock import MagicMock

from attr import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry

from . import init_integration


async def update_sensor_state(
    hass: HomeAssistant,
    entity_id: str,
    mock_sensor_api_instances: MagicMock,
    mock_instance_idx: int,
):
    """Simulate an update trigger from the API."""
    update_ha_state_cb = mock_sensor_api_instances.call_args_list[
        mock_instance_idx
    ].args[3]
    update_ha_state_cb()
    await hass.async_block_till_done()
    return hass.states.get(entity_id)


async def test_sensor_values(
    hass: HomeAssistant,
    mock_sensor1_api: MagicMock,
    mock_sensor2_api: MagicMock,
    mock_sensor_api_instances: MagicMock,
):
    """Test the sensor value callbacks."""
    await init_integration(hass)

    @dataclass
    class SensorTestInstance:
        """Helper class for multiple climate and mock instances."""

        entity_id: str
        mock_instance: MagicMock
        mock_instance_idx: int

    for sensor_test_instance in (
        SensorTestInstance("sensor.washer_state", mock_sensor1_api, 0),
        SensorTestInstance("sensor.dryer_state", mock_sensor2_api, 1),
    ):
        entity_id = sensor_test_instance.entity_id
        mock_instance_idx = sensor_test_instance.mock_instance_idx
        registry = entity_registry.async_get(hass)
        entry = registry.async_get(entity_id)
        assert entry
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "RunningMainCycle"

        state = await update_sensor_state(
            hass, entity_id, mock_sensor_api_instances, mock_instance_idx
        )
        assert state is not None
        state_id = f"{entity_id.split('_')[0]}_time_remaining"
        state = hass.states.get(state_id)
        assert state is not None
        assert state.state == "3540"
