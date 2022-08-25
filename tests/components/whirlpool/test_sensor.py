"""Test the Whirlpool Sensor domain."""
from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant

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
):
    """Test the sensor value callbacks."""
    return
