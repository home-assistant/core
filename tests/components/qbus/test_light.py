"""Test Qbus light entities."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    DOMAIN as LIGHT_DOMAIN,
    EFFECT_OFF,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_mqtt_message, snapshot_platform
from tests.typing import MqttMockHAClient

# 186 = 73% (rounded)
_BRIGHTNESS = 186
_BRIGHTNESS_PCT = 73
_EFFECT = "Summer"
_HS_COLOR = (243.0, 92.0)

_PAYLOAD_DIMMER_STATE_ON = '{"id":"UL15","properties":{"value":60},"type":"state"}'
_PAYLOAD_DIMMER_STATE_BRIGHTNESS = (
    '{"id":"UL15","properties":{"value":' + str(_BRIGHTNESS_PCT) + '},"type":"state"}'
)
_PAYLOAD_DIMMER_STATE_EVENT = '{"id":"UL15","action":"on","type":"event"}'
_PAYLOAD_DIMMER_STATE_OFF = '{"id":"UL15","properties":{"value":0},"type":"state"}'

_PAYLOAD_DIMMER_SET_STATE_ON = '{"id": "UL15", "type": "action", "action": "on"}'
_PAYLOAD_DIMMER_SET_STATE_BRIGHTNESS = (
    '{"id": "UL15", "type": "state", "properties": {"value": '
    + str(_BRIGHTNESS_PCT)
    + "}}"
)
_PAYLOAD_DIMMER_SET_STATE_OFF = '{"id": "UL15", "type": "action", "action": "off"}'

_PAYLOAD_COLOR_STATE_ON = '{"id":"UL100","properties":{"brightness":60},"type":"state"}'
_PAYLOAD_COLOR_STATE_BRIGHTNESS = (
    '{"id": "UL100", "properties":{ "brightness":'
    + str(_BRIGHTNESS_PCT)
    + '},"type":"state"}'
)
_PAYLOAD_COLOR_STATE_COLOR = (
    '{"id": "UL100", "properties":{ "hue":'
    + str(_HS_COLOR[0])
    + ', "saturation":'
    + str(_HS_COLOR[1])
    + '},"type":"state"}'
)
_PAYLOAD_COLOR_STATE_EFFECT = '{"id": "UL100", "properties":{ "presetMovie": 1, "currRegime": "MovieSelect" },"type":"state"}'
_PAYLOAD_COLOR_STATE_EFFECT_OFF = (
    '{"id": "UL100", "properties":{ "currRegime": "ColorWheel" },"type":"state"}'
)
_PAYLOAD_COLOR_STATE_OFF = '{"id":"UL100","properties":{"brightness":0},"type":"state"}'

_PAYLOAD_COLOR_SET_STATE_ON = (
    '{"id": "UL100", "type": "state", "properties": {"on": true}}'
)
_PAYLOAD_COLOR_SET_STATE_BRIGHTNESS = (
    '{"id": "UL100", "type": "state", "properties": {"brightness": '
    + str(_BRIGHTNESS_PCT)
    + "}}"
)
_PAYLOAD_COLOR_SET_STATE_COLOR = (
    '{"id": "UL100", "type": "state", "properties": {"hue": '
    + str(_HS_COLOR[0])
    + ', "saturation": '
    + str(_HS_COLOR[1])
    + "}}"
)
_PAYLOAD_COLOR_SET_STATE_EFFECT = (
    '{"id": "UL100", "type": "state", "properties": {"presetMovie": 1}}'
)
_PAYLOAD_COLOR_SET_STATE_EFFECT_OFF = (
    '{"id": "UL100", "type": "state", "properties": {"currRegime": "ColorWheel"}}'
)
_PAYLOAD_COLOR_SET_STATE_OFF = (
    '{"id": "UL100", "type": "state", "properties": {"on": false}}'
)

_TOPIC_DIMMER_STATE = "cloudapp/QBUSMQTTGW/UL1/UL15/state"
_TOPIC_DIMMER_SET_STATE = "cloudapp/QBUSMQTTGW/UL1/UL15/setState"

_TOPIC_COLOR_STATE = "cloudapp/QBUSMQTTGW/UL1/UL100/state"
_TOPIC_COLOR_SET_STATE = "cloudapp/QBUSMQTTGW/UL1/UL100/setState"

_DIMMER_ENTITY_ID = "light.media_room_media_room"
_COLOR_ENTITY_ID = "light.media_room_tv"


async def test_light(
    hass: HomeAssistant,
    setup_integration_deferred: Callable[[], Awaitable],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test light."""

    with patch("homeassistant.components.qbus.PLATFORMS", [Platform.LIGHT]):
        await setup_integration_deferred()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_dimmer(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    setup_integration: None,
) -> None:
    """Test turning on and off."""

    # Switch ON
    mqtt_mock.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _DIMMER_ENTITY_ID},
        blocking=True,
    )

    _assert_set_state(mqtt_mock, _TOPIC_DIMMER_SET_STATE, _PAYLOAD_DIMMER_SET_STATE_ON)
    await _async_simulate_qbus_response(
        hass, _TOPIC_DIMMER_STATE, _PAYLOAD_DIMMER_STATE_ON
    )

    assert hass.states.get(_DIMMER_ENTITY_ID).state == STATE_ON

    # Set brightness
    mqtt_mock.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: _DIMMER_ENTITY_ID,
            ATTR_BRIGHTNESS: _BRIGHTNESS,
        },
        blocking=True,
    )

    _assert_set_state(
        mqtt_mock, _TOPIC_DIMMER_SET_STATE, _PAYLOAD_DIMMER_SET_STATE_BRIGHTNESS
    )
    await _async_simulate_qbus_response(
        hass, _TOPIC_DIMMER_STATE, _PAYLOAD_DIMMER_STATE_BRIGHTNESS
    )

    entity = hass.states.get(_DIMMER_ENTITY_ID)
    assert entity.state == STATE_ON
    assert entity.attributes.get(ATTR_BRIGHTNESS) == _BRIGHTNESS

    # Switch OFF
    mqtt_mock.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: _DIMMER_ENTITY_ID},
        blocking=True,
    )

    _assert_set_state(mqtt_mock, _TOPIC_DIMMER_SET_STATE, _PAYLOAD_DIMMER_SET_STATE_OFF)
    await _async_simulate_qbus_response(
        hass, _TOPIC_DIMMER_STATE, _PAYLOAD_DIMMER_STATE_OFF
    )

    assert hass.states.get(_DIMMER_ENTITY_ID).state == STATE_OFF


async def test_dimmer_ignore_missing_percentage(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    setup_integration: None,
) -> None:
    """Test ignoring events without percentage."""

    mqtt_mock.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _DIMMER_ENTITY_ID},
        blocking=True,
    )

    await _async_simulate_qbus_response(
        hass, _TOPIC_DIMMER_STATE, _PAYLOAD_DIMMER_STATE_ON
    )

    entity = hass.states.get(_DIMMER_ENTITY_ID)
    brightness = entity.attributes.get(ATTR_BRIGHTNESS)
    assert entity.state == STATE_ON
    assert brightness > 0

    await _async_simulate_qbus_response(
        hass, _TOPIC_DIMMER_STATE, _PAYLOAD_DIMMER_STATE_EVENT
    )

    entity = hass.states.get(_DIMMER_ENTITY_ID)
    assert entity.state == STATE_ON
    assert entity.attributes.get(ATTR_BRIGHTNESS) == brightness


async def test_color(
    hass: HomeAssistant,
    mqtt_mock: MqttMockHAClient,
    setup_integration: None,
) -> None:
    """Test turning on and off."""

    # Switch ON
    mqtt_mock.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _COLOR_ENTITY_ID},
        blocking=True,
    )

    _assert_set_state(mqtt_mock, _TOPIC_COLOR_SET_STATE, _PAYLOAD_COLOR_SET_STATE_ON)
    await _async_simulate_qbus_response(
        hass, _TOPIC_COLOR_STATE, _PAYLOAD_COLOR_STATE_ON
    )

    assert hass.states.get(_COLOR_ENTITY_ID).state == STATE_ON

    # Set brightness
    mqtt_mock.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: _COLOR_ENTITY_ID,
            ATTR_BRIGHTNESS: _BRIGHTNESS,
        },
        blocking=True,
    )

    _assert_set_state(
        mqtt_mock, _TOPIC_COLOR_SET_STATE, _PAYLOAD_COLOR_SET_STATE_BRIGHTNESS
    )
    await _async_simulate_qbus_response(
        hass, _TOPIC_COLOR_STATE, _PAYLOAD_COLOR_STATE_BRIGHTNESS
    )

    entity = hass.states.get(_COLOR_ENTITY_ID)
    assert entity.state == STATE_ON
    assert entity.attributes.get(ATTR_BRIGHTNESS) == _BRIGHTNESS

    # Set effect
    mqtt_mock.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: _COLOR_ENTITY_ID,
            ATTR_EFFECT: _EFFECT,
        },
        blocking=True,
    )

    _assert_set_state(
        mqtt_mock, _TOPIC_COLOR_SET_STATE, _PAYLOAD_COLOR_SET_STATE_EFFECT
    )
    await _async_simulate_qbus_response(
        hass, _TOPIC_COLOR_STATE, _PAYLOAD_COLOR_STATE_EFFECT
    )

    entity = hass.states.get(_COLOR_ENTITY_ID)
    assert entity.state == STATE_ON
    assert entity.attributes.get(ATTR_EFFECT) == _EFFECT

    # Stop effect
    mqtt_mock.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: _COLOR_ENTITY_ID,
            ATTR_EFFECT: EFFECT_OFF,
        },
        blocking=True,
    )

    _assert_set_state(
        mqtt_mock, _TOPIC_COLOR_SET_STATE, _PAYLOAD_COLOR_SET_STATE_EFFECT_OFF
    )
    await _async_simulate_qbus_response(
        hass, _TOPIC_COLOR_STATE, _PAYLOAD_COLOR_STATE_EFFECT_OFF
    )

    entity = hass.states.get(_COLOR_ENTITY_ID)
    assert entity.state == STATE_ON
    assert entity.attributes.get(ATTR_EFFECT) == EFFECT_OFF

    # Set color
    mqtt_mock.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {
            ATTR_ENTITY_ID: _COLOR_ENTITY_ID,
            ATTR_HS_COLOR: _HS_COLOR,
        },
        blocking=True,
    )

    _assert_set_state(mqtt_mock, _TOPIC_COLOR_SET_STATE, _PAYLOAD_COLOR_SET_STATE_COLOR)
    await _async_simulate_qbus_response(
        hass, _TOPIC_COLOR_STATE, _PAYLOAD_COLOR_STATE_COLOR
    )

    entity = hass.states.get(_COLOR_ENTITY_ID)
    assert entity.state == STATE_ON
    assert entity.attributes.get(ATTR_HS_COLOR) == _HS_COLOR

    # Switch OFF
    mqtt_mock.reset_mock()
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: _COLOR_ENTITY_ID},
        blocking=True,
    )

    _assert_set_state(mqtt_mock, _TOPIC_COLOR_SET_STATE, _PAYLOAD_COLOR_SET_STATE_OFF)
    await _async_simulate_qbus_response(
        hass, _TOPIC_COLOR_STATE, _PAYLOAD_COLOR_STATE_OFF
    )

    assert hass.states.get(_COLOR_ENTITY_ID).state == STATE_OFF


def _assert_set_state(mqtt_mock: MqttMockHAClient, topic: str, payload: str) -> None:
    mqtt_mock.async_publish.assert_called_once_with(
        topic,
        payload,
        0,
        False,
        message_expiry_interval=None,
    )


async def _async_simulate_qbus_response(
    hass: HomeAssistant, topic: str, payload: str
) -> None:
    async_fire_mqtt_message(hass, topic, payload)
    await hass.async_block_till_done()
