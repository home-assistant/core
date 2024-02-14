"""Test DROP select entities."""

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .common import (
    TEST_DATA_HUB,
    TEST_DATA_HUB_RESET,
    TEST_DATA_HUB_TOPIC,
    config_entry_hub,
)

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def test_selects_hub(hass: HomeAssistant, mqtt_mock: MqttMockHAClient) -> None:
    """Test DROP binary sensors for hubs."""
    entry = config_entry_hub()
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    protect_mode_select_name = "select.hub_drop_1_c0ffee_protect_mode"
    protect_mode_select = hass.states.get(protect_mode_select_name)
    assert protect_mode_select
    assert protect_mode_select.attributes.get(ATTR_OPTIONS) == [
        "away",
        "home",
        "schedule",
    ]

    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB_RESET)
    await hass.async_block_till_done()
    protect_mode_select = hass.states.get(protect_mode_select_name)
    assert protect_mode_select
    assert protect_mode_select.attributes.get(ATTR_OPTIONS) == [
        "away",
        "home",
        "schedule",
    ]

    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB)
    await hass.async_block_till_done()

    protect_mode_select = hass.states.get(protect_mode_select_name)
    assert protect_mode_select
    assert protect_mode_select.state == "home"

    mqtt_mock.async_publish.reset_mock()
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_OPTION: "away", ATTR_ENTITY_ID: protect_mode_select_name},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert len(mqtt_mock.async_publish.mock_calls) == 1

    # Simulate response of the device
    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB_RESET)
    await hass.async_block_till_done()

    protect_mode_select = hass.states.get(protect_mode_select_name)
    assert protect_mode_select
    assert protect_mode_select.state == "away"
