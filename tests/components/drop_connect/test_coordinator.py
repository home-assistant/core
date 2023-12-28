"""Test DROP coordinator."""
from homeassistant.components.drop_connect.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import TEST_DATA_HUB, TEST_DATA_HUB_RESET, TEST_DATA_HUB_TOPIC

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClient


async def test_bad_json(
    hass: HomeAssistant, config_entry_hub, mqtt_mock: MqttMockHAClient
) -> None:
    """Test bad JSON."""
    config_entry_hub.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    current_flow_sensor_name = "sensor.hub_drop_1_c0ffee_water_flow_rate"
    hass.states.async_set(current_flow_sensor_name, STATE_UNKNOWN)

    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, "{BAD JSON}")
    await hass.async_block_till_done()

    current_flow_sensor = hass.states.get(current_flow_sensor_name)
    assert current_flow_sensor
    assert current_flow_sensor.state == STATE_UNKNOWN


async def test_unload(
    hass: HomeAssistant, config_entry_hub, mqtt_mock: MqttMockHAClient
) -> None:
    """Test entity unload."""
    # Load the hub device
    config_entry_hub.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    current_flow_sensor_name = "sensor.hub_drop_1_c0ffee_water_flow_rate"
    hass.states.async_set(current_flow_sensor_name, STATE_UNKNOWN)

    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB_RESET)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, TEST_DATA_HUB_TOPIC, TEST_DATA_HUB)
    await hass.async_block_till_done()

    current_flow_sensor = hass.states.get(current_flow_sensor_name)
    assert current_flow_sensor
    assert round(float(current_flow_sensor.state), 1) == 5.8

    # Unload the device
    await hass.config_entries.async_unload(config_entry_hub.entry_id)
    await hass.async_block_till_done()

    assert config_entry_hub.state is ConfigEntryState.NOT_LOADED

    # Verify sensor is unavailable
    current_flow_sensor = hass.states.get(current_flow_sensor_name)
    assert current_flow_sensor
    assert current_flow_sensor.state == STATE_UNAVAILABLE


async def test_no_mqtt(hass: HomeAssistant, config_entry_hub) -> None:
    """Test no MQTT."""
    config_entry_hub.add_to_hass(hass)
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    protect_mode_select_name = "select.hub_drop_1_c0ffee_protect_mode"
    protect_mode_select = hass.states.get(protect_mode_select_name)
    assert protect_mode_select is None
