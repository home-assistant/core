"""Test DROP coordinator."""

from homeassistant.components.drop.const import DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import TEST_DATA_HUB_TOPIC

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def test_bad_json(
    hass: HomeAssistant, config_entry_hub, mqtt_mock: MqttMockHAClient
) -> None:
    """Test bad JSON."""
    config_entry_hub.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    currentFlowSensorName = "sensor.hub_drop_1_c0ffee_water_flow_rate"
    currentFlowSensor = hass.states.get(currentFlowSensorName)
    assert currentFlowSensor
    assert currentFlowSensor.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, "{BAD JSON}")
    await hass.async_block_till_done()

    currentFlowSensor = hass.states.get(currentFlowSensorName)
    assert currentFlowSensor
    assert currentFlowSensor.state == STATE_UNKNOWN


async def test_no_mqtt(hass: HomeAssistant, config_entry_hub) -> None:
    """Test no MQTT."""
    config_entry_hub.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    protectModeSelectName = "select.hub_drop_1_c0ffee_protect_mode"
    protectModeSelect = hass.states.get(protectModeSelectName)
    assert protectModeSelect is None
