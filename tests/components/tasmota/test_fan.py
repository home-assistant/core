"""The tests for the Tasmota fan platform."""
import copy
import json
from unittest.mock import patch

from hatasmota.utils import (
    get_topic_stat_result,
    get_topic_tele_state,
    get_topic_tele_will,
)
import pytest
from voluptuous import MultipleInvalid

from homeassistant.components import fan
from homeassistant.components.tasmota.const import DEFAULT_PREFIX
from homeassistant.const import ATTR_ASSUMED_STATE, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant

from .test_common import (
    DEFAULT_CONFIG,
    help_test_availability,
    help_test_availability_discovery_update,
    help_test_availability_poll_state,
    help_test_availability_when_connection_lost,
    help_test_discovery_device_remove,
    help_test_discovery_removal,
    help_test_discovery_update_unchanged,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
)

from tests.common import async_fire_mqtt_message
from tests.components.fan import common
from tests.typing import MqttMockHAClient, MqttMockPahoClient


async def test_controlling_state_via_mqtt(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["if"] = 1
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("fan.tasmota")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    await hass.async_block_till_done()
    state = hass.states.get("fan.tasmota")
    assert state.state == STATE_OFF
    assert state.attributes["percentage"] is None
    assert state.attributes["supported_features"] == fan.SUPPORT_SET_SPEED
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"FanSpeed":1}')
    state = hass.states.get("fan.tasmota")
    assert state.state == STATE_ON
    assert state.attributes["percentage"] == 33

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"FanSpeed":2}')
    state = hass.states.get("fan.tasmota")
    assert state.state == STATE_ON
    assert state.attributes["percentage"] == 66

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"FanSpeed":3}')
    state = hass.states.get("fan.tasmota")
    assert state.state == STATE_ON
    assert state.attributes["percentage"] == 100

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"FanSpeed":0}')
    state = hass.states.get("fan.tasmota")
    assert state.state == STATE_OFF
    assert state.attributes["percentage"] == 0

    async_fire_mqtt_message(hass, "tasmota_49A3BC/stat/RESULT", '{"FanSpeed":1}')
    state = hass.states.get("fan.tasmota")
    assert state.state == STATE_ON
    assert state.attributes["percentage"] == 33

    async_fire_mqtt_message(hass, "tasmota_49A3BC/stat/RESULT", '{"FanSpeed":0}')
    state = hass.states.get("fan.tasmota")
    assert state.state == STATE_OFF
    assert state.attributes["percentage"] == 0


async def test_sending_mqtt_commands(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test the sending MQTT commands."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["if"] = 1
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    await hass.async_block_till_done()
    state = hass.states.get("fan.tasmota")
    assert state.state == STATE_OFF
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()

    # Turn the fan on and verify MQTT message is sent
    await common.async_turn_on(hass, "fan.tasmota")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/FanSpeed", "2", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Tasmota is not optimistic, the state should still be off
    state = hass.states.get("fan.tasmota")
    assert state.state == STATE_OFF

    # Turn the fan off and verify MQTT message is sent
    await common.async_turn_off(hass, "fan.tasmota")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/FanSpeed", "0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Set speed percentage and verify MQTT message is sent
    await common.async_set_percentage(hass, "fan.tasmota", 0)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/FanSpeed", "0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Set speed percentage and verify MQTT message is sent
    await common.async_set_percentage(hass, "fan.tasmota", 15)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/FanSpeed", "1", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Set speed percentage and verify MQTT message is sent
    await common.async_set_percentage(hass, "fan.tasmota", 50)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/FanSpeed", "2", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Set speed percentage and verify MQTT message is sent
    await common.async_set_percentage(hass, "fan.tasmota", 90)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/FanSpeed", "3", 0, False
    )

    # Test the last known fan speed is restored
    # First, get a fan speed update
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"FanSpeed":3}')
    state = hass.states.get("fan.tasmota")
    assert state.state == STATE_ON
    assert state.attributes["percentage"] == 100
    mqtt_mock.async_publish.reset_mock()

    # Then turn the fan off and get a fan state update
    await common.async_turn_off(hass, "fan.tasmota")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/FanSpeed", "0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    async_fire_mqtt_message(hass, "tasmota_49A3BC/stat/RESULT", '{"FanSpeed":0}')
    state = hass.states.get("fan.tasmota")
    assert state.state == STATE_OFF
    assert state.attributes["percentage"] == 0
    mqtt_mock.async_publish.reset_mock()

    # Finally, turn the fan on again and verify MQTT message is sent with last known speed
    await common.async_turn_on(hass, "fan.tasmota")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/FanSpeed", "3", 0, False
    )
    mqtt_mock.async_publish.reset_mock()


async def test_invalid_fan_speed_percentage(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test the sending MQTT commands."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["if"] = 1
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    await hass.async_block_till_done()
    state = hass.states.get("fan.tasmota")
    assert state.state == STATE_OFF
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()

    # Set an unsupported speed and verify MQTT message is not sent
    with pytest.raises(MultipleInvalid) as excinfo:
        await common.async_set_percentage(hass, "fan.tasmota", 101)
    assert "value must be at most 100" in str(excinfo.value)
    mqtt_mock.async_publish.assert_not_called()


async def test_availability_when_connection_lost(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test availability after MQTT disconnection."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["dn"] = "Test"
    config["if"] = 1
    await help_test_availability_when_connection_lost(
        hass, mqtt_client_mock, mqtt_mock, Platform.FAN, config
    )


async def test_availability(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test availability."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["dn"] = "Test"
    config["if"] = 1
    await help_test_availability(hass, mqtt_mock, Platform.FAN, config)


async def test_availability_discovery_update(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test availability discovery update."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["dn"] = "Test"
    config["if"] = 1
    await help_test_availability_discovery_update(hass, mqtt_mock, Platform.FAN, config)


async def test_availability_poll_state(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test polling after MQTT connection (re)established."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["if"] = 1
    poll_topic = "tasmota_49A3BC/cmnd/STATE"
    await help_test_availability_poll_state(
        hass, mqtt_client_mock, mqtt_mock, Platform.FAN, config, poll_topic, ""
    )


async def test_discovery_removal_fan(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    caplog: pytest.LogCaptureFixture,
    setup_tasmota,
) -> None:
    """Test removal of discovered fan."""
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config1["dn"] = "Test"
    config1["if"] = 1
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config2["dn"] = "Test"
    config2["if"] = 0

    await help_test_discovery_removal(
        hass, mqtt_mock, caplog, Platform.FAN, config1, config2
    )


async def test_discovery_update_unchanged_fan(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    caplog: pytest.LogCaptureFixture,
    setup_tasmota,
) -> None:
    """Test update of discovered fan."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["dn"] = "Test"
    config["if"] = 1
    with patch(
        "homeassistant.components.tasmota.fan.TasmotaFan.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock, caplog, Platform.FAN, config, discovery_update
        )


async def test_discovery_device_remove(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test device registry remove."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["dn"] = "Test"
    config["if"] = 1
    unique_id = f"{DEFAULT_CONFIG['mac']}_fan_fan_ifan"
    await help_test_discovery_device_remove(
        hass, mqtt_mock, Platform.FAN, unique_id, config
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["dn"] = "Test"
    config["if"] = 1
    topics = [
        get_topic_stat_result(config),
        get_topic_tele_state(config),
        get_topic_tele_will(config),
    ]
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock, Platform.FAN, config, topics
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["dn"] = "Test"
    config["if"] = 1
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, Platform.FAN, config
    )
