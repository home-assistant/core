"""The tests for the Tasmota switch platform."""
import copy
import json
from unittest.mock import patch

from hatasmota.utils import (
    get_topic_stat_result,
    get_topic_tele_state,
    get_topic_tele_will,
)
import pytest

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
from tests.components.switch import common
from tests.typing import MqttMockHAClient, MqttMockPahoClient


async def test_controlling_state_via_mqtt(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    await hass.async_block_till_done()
    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON"}')

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"OFF"}')

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "tasmota_49A3BC/stat/RESULT", '{"POWER":"ON"}')

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "tasmota_49A3BC/stat/RESULT", '{"POWER":"OFF"}')

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF


async def test_sending_mqtt_commands(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test the sending MQTT commands."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    await hass.async_block_till_done()
    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()

    # Turn the switch on and verify MQTT message is sent
    await common.async_turn_on(hass, "switch.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Power1", "ON", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Tasmota is not optimistic, the state should still be off
    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF

    # Turn the switch off and verify MQTT message is sent
    await common.async_turn_off(hass, "switch.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Power1", "OFF", 0, False
    )

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF


async def test_relay_as_light(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test relay does not show up as switch in light mode."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    config["so"]["30"] = 1  # Enforce Home Assistant auto-discovery as light
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test")
    assert state is None
    state = hass.states.get("light.test")
    assert state is not None


async def test_availability_when_connection_lost(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test availability after MQTT disconnection."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    await help_test_availability_when_connection_lost(
        hass, mqtt_client_mock, mqtt_mock, Platform.SWITCH, config
    )


async def test_availability(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test availability."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    await help_test_availability(hass, mqtt_mock, Platform.SWITCH, config)


async def test_availability_discovery_update(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test availability discovery update."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    await help_test_availability_discovery_update(
        hass, mqtt_mock, Platform.SWITCH, config
    )


async def test_availability_poll_state(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    mqtt_mock: MqttMockHAClient,
    setup_tasmota,
) -> None:
    """Test polling after MQTT connection (re)established."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    poll_topic = "tasmota_49A3BC/cmnd/STATE"
    await help_test_availability_poll_state(
        hass, mqtt_client_mock, mqtt_mock, Platform.SWITCH, config, poll_topic, ""
    )


async def test_discovery_removal_switch(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    caplog: pytest.LogCaptureFixture,
    setup_tasmota,
) -> None:
    """Test removal of discovered switch."""
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config1["rl"][0] = 1
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config2["rl"][0] = 0

    await help_test_discovery_removal(
        hass, mqtt_mock, caplog, Platform.SWITCH, config1, config2
    )


async def test_discovery_removal_relay_as_light(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    caplog: pytest.LogCaptureFixture,
    setup_tasmota,
) -> None:
    """Test removal of discovered relay as light."""
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config1["rl"][0] = 1
    config1["so"]["30"] = 0  # Disable Home Assistant auto-discovery as light
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config2["rl"][0] = 1
    config2["so"]["30"] = 1  # Enforce Home Assistant auto-discovery as light

    await help_test_discovery_removal(
        hass, mqtt_mock, caplog, Platform.SWITCH, config1, config2
    )


async def test_discovery_update_unchanged_switch(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    caplog: pytest.LogCaptureFixture,
    setup_tasmota,
) -> None:
    """Test update of discovered switch."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    with patch(
        "homeassistant.components.tasmota.switch.TasmotaSwitch.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock, caplog, Platform.SWITCH, config, discovery_update
        )


async def test_discovery_device_remove(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test device registry remove."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    unique_id = f"{DEFAULT_CONFIG['mac']}_switch_relay_0"
    await help_test_discovery_device_remove(
        hass, mqtt_mock, Platform.SWITCH, unique_id, config
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    topics = [
        get_topic_stat_result(config),
        get_topic_tele_state(config),
        get_topic_tele_will(config),
    ]
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock, Platform.SWITCH, config, topics
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock: MqttMockHAClient, setup_tasmota
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, Platform.SWITCH, config
    )
