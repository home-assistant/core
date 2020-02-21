"""The tests for the MQTT remote platform."""

from homeassistant.components import remote
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.setup import async_setup_component

from tests.common import async_fire_mqtt_message
from tests.components.remote import common


async def test_sending_mqtt_commands_and_default_optimistic(hass, mqtt_mock):
    """Test optimistic mode without state topic."""
    assert await async_setup_component(
        hass,
        remote.DOMAIN,
        {
            remote.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "payload_on": "ON",
                "payload_off": "OFF",
            }
        },
    )

    state = hass.states.get("remote.test")
    assert state.state is STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "remote.test")

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("remote.test")
    assert state.state is STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "remote.test")


async def test_sending_mqtt_commands_and_explicit_optimistic(hass, mqtt_mock):
    """Test optimistic mode without state topic."""
    assert await async_setup_component(
        hass,
        remote.DOMAIN,
        {
            remote.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "payload_on": "ON",
                "payload_off": "OFF",
                "optimistic": True,
                "commands": {
                    "vol_up": {"command": "volume_up"},
                    "vol_down": {"command": "volume_down"},
                },
            }
        },
    )

    await common.async_send_command(hass, "vol_up", "remote.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "volume_up", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_send_command(hass, "vol_down", "remote.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "volume_down", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    state = hass.states.get("remote.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "remote.test")

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("remote.test")
    assert state.state is STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "remote.test")

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("remote.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)


async def test_receiving_mqtt_state_with_optimistic_off(hass, mqtt_mock):
    """Test optimistic mode without state topic."""
    assert await async_setup_component(
        hass,
        remote.DOMAIN,
        {
            remote.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "payload_on": "ON",
                "payload_off": "OFF",
                "state_topic": "state-topic",
                "state_on": "STATE_ON",
                "state_off": "STATE_OFF",
                "optimistic": False,
            }
        },
    )

    state = hass.states.get("remote.test")
    assert state.state is STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Try with payload_on command, shouldn't work since state_on was defined
    async_fire_mqtt_message(hass, "state-topic", "ON")

    state = hass.states.get("remote.test")
    assert state.state is STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Try with state_on command, should work
    async_fire_mqtt_message(hass, "state-topic", "STATE_ON")

    state = hass.states.get("remote.test")
    assert state.state is STATE_ON
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Try with payload_off command, shouldn't work since state_off was defined
    async_fire_mqtt_message(hass, "state-topic", "OFF")

    state = hass.states.get("remote.test")
    assert state.state is STATE_ON
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Try with state_off command, should work
    async_fire_mqtt_message(hass, "state-topic", "STATE_OFF")

    state = hass.states.get("remote.test")
    assert state.state is STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    assert await async_setup_component(
        hass,
        remote.DOMAIN,
        {
            remote.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "payload_on": "ON",
                "payload_off": "OFF",
                "availability_topic": "availability-topic",
            }
        },
    )

    state = hass.states.get("remote.test")
    assert state.state is STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "online")

    state = hass.states.get("remote.test")
    assert state.state is not STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "offline")

    state = hass.states.get("remote.test")
    assert state.state is STATE_UNAVAILABLE


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    assert await async_setup_component(
        hass,
        remote.DOMAIN,
        {
            remote.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "payload_on": "ON",
                "payload_off": "OFF",
                "availability_topic": "availability-topic",
                "payload_available": "good",
                "payload_not_available": "nogood",
            }
        },
    )

    state = hass.states.get("remote.test")
    assert state.state is STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "good")

    state = hass.states.get("remote.test")
    assert state.state is not STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "nogood")

    state = hass.states.get("remote.test")
    assert state.state is STATE_UNAVAILABLE
