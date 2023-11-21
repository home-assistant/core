"""Test DROP select entities."""

from homeassistant.components.drop.const import DOMAIN as DROP_DOMAIN
from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import TEST_DATA_HUB, TEST_DATA_HUB_TOPIC

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def test_selects_hub(
    hass: HomeAssistant, config_entry_hub, mqtt_mock: MqttMockHAClient
) -> None:
    """Test DROP binary sensors for hubs."""
    config_entry_hub.add_to_hass(hass)
    assert await async_setup_component(hass, DROP_DOMAIN, {})
    await hass.async_block_till_done()

    protectModeSelectName = "select.hub_drop_1_c0ffee_protect_mode"
    protectModeSelect = hass.states.get(protectModeSelectName)
    assert protectModeSelect
    assert protectModeSelect.attributes.get(ATTR_OPTIONS) == [
        "AWAY",
        "HOME",
        "SCHEDULE",
    ]
    assert protectModeSelect.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB)
    await hass.async_block_till_done()

    protectModeSelect = hass.states.get(protectModeSelectName)
    assert protectModeSelect
    assert protectModeSelect.state == "HOME"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_OPTION: "AWAY", ATTR_ENTITY_ID: protectModeSelectName},
        blocking=True,
    )
    await hass.async_block_till_done()

    protectModeSelect = hass.states.get(protectModeSelectName)
    assert protectModeSelect
    assert (
        protectModeSelect.state == "HOME"
    )  # async select does not actually change the value locally; it changes on update from the hub
