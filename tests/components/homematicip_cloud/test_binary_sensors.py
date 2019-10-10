"""Tests for HomematicIP Cloud lights."""
import logging

from tests.components.homematicip_cloud.helper import (
    async_manipulate_test_data,
    get_and_check_entity_basics,
)

_LOGGER = logging.getLogger(__name__)


async def test_hmip_sam(hass, default_mock_hap):
    """Test HomematicipLight."""
    entity_id = "binary_sensor.garagentor"
    entity_name = "Garagentor"
    device_model = "HmIP-SAM"

    ha_entity, hmip_device = get_and_check_entity_basics(
        hass, default_mock_hap, entity_id, entity_name, device_model
    )

    assert ha_entity.state == "on"
    assert ha_entity.attributes["acceleration_sensor_mode"] == "FLAT_DECT"
    assert ha_entity.attributes["acceleration_sensor_neutral_position"] == "VERTICAL"
    assert ha_entity.attributes["acceleration_sensor_sensitivity"] == "SENSOR_RANGE_4G"
    assert ha_entity.attributes["acceleration_sensor_trigger_angle"] == 45
    service_call_counter = len(hmip_device.mock_calls)

    await async_manipulate_test_data(
        hass, hmip_device, "accelerationSensorTriggered", False
    )
    ha_entity = hass.states.get(entity_id)
    assert ha_entity.state == "off"
    assert len(hmip_device.mock_calls) == service_call_counter + 1

    await async_manipulate_test_data(
        hass, hmip_device, "accelerationSensorTriggered", True
    )
    ha_entity = hass.states.get(entity_id)
    assert ha_entity.state == "on"
    assert len(hmip_device.mock_calls) == service_call_counter + 2
