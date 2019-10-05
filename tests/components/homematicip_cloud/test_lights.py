"""Tests for HomematicIP Cloud lights."""
import logging

from tests.components.homematicip_cloud.helper import (
    async_manipulate_test_data,
    get_and_check_entity_basics,
)

_LOGGER = logging.getLogger(__name__)


async def test_hmip_light(hass, default_mock_hap):
    """Test HomematicipLight."""
    entity_id = "light.treppe"
    entity_name = "Treppe"
    device_model = "HmIP-BSL"

    ha_entity, hmip_device = get_and_check_entity_basics(
        hass, default_mock_hap, entity_id, entity_name, device_model
    )

    assert ha_entity.state == "on"

    service_call_counter = len(hmip_device.mock_calls)
    await hass.services.async_call(
        "light", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 1
    assert hmip_device.mock_calls[-1][0] == "turn_off"
    await async_manipulate_test_data(hass, hmip_device, "on", False)
    ha_entity = hass.states.get(entity_id)
    assert ha_entity.state == "off"

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 3
    assert hmip_device.mock_calls[-1][0] == "turn_on"
    await async_manipulate_test_data(hass, hmip_device, "on", True)
    ha_entity = hass.states.get(entity_id)
    assert ha_entity.state == "on"


# HomematicipLightMeasuring
# HomematicipDimmer


async def test_hmip_notification_light(hass, default_mock_hap):
    """Test HomematicipNotificationLight."""
    entity_id = "light.treppe_top_notification"
    entity_name = "Treppe Top Notification"
    device_model = "HmIP-BSL"

    ha_entity, hmip_device = get_and_check_entity_basics(
        hass, default_mock_hap, entity_id, entity_name, device_model
    )

    assert ha_entity.state == "off"
    service_call_counter = len(hmip_device.mock_calls)

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": entity_id}, blocking=True
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 1
    assert hmip_device.mock_calls[-1][0] == "set_rgb_dim_level"
    await async_manipulate_test_data(hass, hmip_device, "dimLevel", 100, 2)
    ha_entity = hass.states.get(entity_id)
    assert ha_entity.state == "on"

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": entity_id}, blocking=True
    )
    assert len(hmip_device.mock_calls) == service_call_counter + 3
    assert hmip_device.mock_calls[-1][0] == "set_rgb_dim_level"
    await async_manipulate_test_data(hass, hmip_device, "dimLevel", 0, 2)
    ha_entity = hass.states.get(entity_id)
    assert ha_entity.state == "off"
