"""Test the Whirlpool Sensor domain."""
from unittest.mock import AsyncMock, MagicMock

from attr import dataclass

from homeassistant.core import HomeAssistant

from . import init_integration

# from attr import dataclass
# import pytest
# import whirlpool


# from homeassistant.helpers import entity_registry as er

# from . import init_integration


async def update_sensor_state(
    hass: HomeAssistant,
    entity_id: str,
    mock_aircon_api_instances: MagicMock,
    mock_instance_idx: int,
):
    """Simulate an update trigger from the API."""
    update_ha_state_cb = mock_aircon_api_instances.call_args_list[
        mock_instance_idx
    ].args[3]
    update_ha_state_cb()
    await hass.async_block_till_done()
    return hass.states.get(entity_id)


async def test_sensor_values(
    hass: HomeAssistant,
    mock_sensor_api_instances: MagicMock,
    mock_sensor1_api: MagicMock,
    mock_sensor2_api: MagicMock,
    mock_aircon_api_instances: MagicMock,
    mock_aircon1_api: MagicMock,
):
    """Test the sensor value callbacks."""
    mock_sensor1_api.connect = AsyncMock()
    await init_integration(hass)

    @dataclass
    class SensorTestInstance:
        """Helper class for multiple climate and mock instances."""

        entity_id: str
        mock_instance: MagicMock
        mock_instance_idx: int

    for sensor_test_instance in (
        SensorTestInstance("sensor.said3", mock_sensor1_api, 0),
        SensorTestInstance("sensor.said4", mock_sensor2_api, 1),
    ):
        entity_id = sensor_test_instance.entity_id
        # mock_instance = sensor_test_instance.mock_instance
        # mock_instance_idx = sensor_test_instance.mock_instance_idx
        # state = hass.states.get(entity_id)
        assert entity_id
