"""Test Qbus cover entities."""

from unittest.mock import AsyncMock

from qbusmqttapi.state import QbusMqttShutterState

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
)
from homeassistant.core import HomeAssistant

from tests.common import async_fire_mqtt_message

_PAYLOAD_UDS_STATE_CLOSED = '{"id":"UL30","properties":{"state":"down"},"type":"state"}'
_PAYLOAD_UDS_STATE_OPENED = '{"id":"UL30","properties":{"state":"up"},"type":"state"}'
_PAYLOAD_UDS_STATE_STOPPED = (
    '{"id":"UL30","properties":{"state":"stop"},"type":"state"}'
)

_PAYLOAD_POS_STATE_CLOSED = (
    '{"id":"UL32","properties":{"shutterPosition":0},"type":"event"}'
)
_PAYLOAD_POS_STATE_OPENED = (
    '{"id":"UL32","properties":{"shutterPosition":100},"type":"event"}'
)
_PAYLOAD_POS_STATE_POSITION = (
    '{"id":"UL32","properties":{"shutterPosition":50},"type":"event"}'
)

_PAYLOAD_SLAT_STATE_CLOSED = (
    '{"id":"UL31","properties":{"slatPosition":0},"type":"event"}'
)
_PAYLOAD_SLAT_STATE_FULLY_CLOSED = (
    '{"id":"UL31","properties":{"slatPosition":0,"shutterPosition":0},"type":"event"}'
)
_PAYLOAD_SLAT_STATE_OPENED = (
    '{"id":"UL31","properties":{"slatPosition":50},"type":"event"}'
)
_PAYLOAD_SLAT_STATE_POSITION = (
    '{"id":"UL31","properties":{"slatPosition":75},"type":"event"}'
)

_TOPIC_UDS_STATE = "cloudapp/QBUSMQTTGW/UL1/UL30/state"
_TOPIC_POS_STATE = "cloudapp/QBUSMQTTGW/UL1/UL32/state"
_TOPIC_SLAT_STATE = "cloudapp/QBUSMQTTGW/UL1/UL31/state"

_ENTITY_ID_UDS = "cover.curtains"
_ENTITY_ID_POS = "cover.blinds"
_ENTITY_ID_SLAT = "cover.slats"


async def test_cover_up_down_stop(
    hass: HomeAssistant, setup_integration: None, mock_publish_state: AsyncMock
) -> None:
    """Test cover up, down and stop."""

    attributes = hass.states.get(_ENTITY_ID_UDS).attributes
    assert attributes.get("supported_features") == (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    # Cover open
    mock_publish_state.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: _ENTITY_ID_UDS},
        blocking=True,
    )

    publish_state = _get_publish_state(mock_publish_state)
    assert publish_state.read_state() == "up"

    # Simulate response
    async_fire_mqtt_message(hass, _TOPIC_UDS_STATE, _PAYLOAD_UDS_STATE_OPENED)
    await hass.async_block_till_done()

    assert hass.states.get(_ENTITY_ID_UDS).state == CoverState.OPEN

    # Cover close
    mock_publish_state.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: _ENTITY_ID_UDS},
        blocking=True,
    )

    publish_state = _get_publish_state(mock_publish_state)
    assert publish_state.read_state() == "down"

    # Simulate response
    async_fire_mqtt_message(hass, _TOPIC_UDS_STATE, _PAYLOAD_UDS_STATE_CLOSED)
    await hass.async_block_till_done()

    assert hass.states.get(_ENTITY_ID_UDS).state == CoverState.OPEN

    # Cover stop
    mock_publish_state.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: _ENTITY_ID_UDS},
        blocking=True,
    )

    publish_state = _get_publish_state(mock_publish_state)
    assert publish_state.read_state() == "stop"

    # Simulate response
    async_fire_mqtt_message(hass, _TOPIC_UDS_STATE, _PAYLOAD_UDS_STATE_STOPPED)
    await hass.async_block_till_done()

    assert hass.states.get(_ENTITY_ID_UDS).state == CoverState.CLOSED


async def test_cover_position(
    hass: HomeAssistant, setup_integration: None, mock_publish_state: AsyncMock
) -> None:
    """Test cover positions."""

    attributes = hass.states.get(_ENTITY_ID_POS).attributes
    assert attributes.get("supported_features") == (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    # Cover open
    mock_publish_state.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: _ENTITY_ID_POS},
        blocking=True,
    )

    publish_state = _get_publish_state(mock_publish_state)
    assert publish_state.read_position() == 100

    async_fire_mqtt_message(hass, _TOPIC_POS_STATE, _PAYLOAD_POS_STATE_OPENED)
    await hass.async_block_till_done()

    entity_state = hass.states.get(_ENTITY_ID_POS)
    assert entity_state.state == CoverState.OPEN
    assert entity_state.attributes[ATTR_CURRENT_POSITION] == 100

    # Cover position
    mock_publish_state.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: _ENTITY_ID_POS, ATTR_POSITION: 50},
        blocking=True,
    )

    publish_state = _get_publish_state(mock_publish_state)
    assert publish_state.read_position() == 50

    async_fire_mqtt_message(hass, _TOPIC_POS_STATE, _PAYLOAD_POS_STATE_POSITION)
    await hass.async_block_till_done()

    entity_state = hass.states.get(_ENTITY_ID_POS)
    assert entity_state.state == CoverState.OPEN
    assert entity_state.attributes[ATTR_CURRENT_POSITION] == 50

    # Cover close
    mock_publish_state.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: _ENTITY_ID_POS},
        blocking=True,
    )

    publish_state = _get_publish_state(mock_publish_state)
    assert publish_state.read_position() == 0

    async_fire_mqtt_message(hass, _TOPIC_POS_STATE, _PAYLOAD_POS_STATE_CLOSED)
    await hass.async_block_till_done()

    entity_state = hass.states.get(_ENTITY_ID_POS)
    assert entity_state.state == CoverState.CLOSED
    assert entity_state.attributes[ATTR_CURRENT_POSITION] == 0


async def test_cover_slats(
    hass: HomeAssistant, setup_integration: None, mock_publish_state: AsyncMock
) -> None:
    """Test cover slats."""

    attributes = hass.states.get(_ENTITY_ID_SLAT).attributes
    assert attributes.get("supported_features") == (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )

    # Start with a fully closed cover
    mock_publish_state.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: _ENTITY_ID_SLAT},
        blocking=True,
    )

    publish_state = _get_publish_state(mock_publish_state)
    assert publish_state.read_position() == 0
    assert publish_state.read_slat_position() == 0

    async_fire_mqtt_message(hass, _TOPIC_SLAT_STATE, _PAYLOAD_SLAT_STATE_FULLY_CLOSED)
    await hass.async_block_till_done()

    entity_state = hass.states.get(_ENTITY_ID_SLAT)
    assert entity_state.state == CoverState.CLOSED
    assert entity_state.attributes[ATTR_CURRENT_POSITION] == 0
    assert entity_state.attributes[ATTR_CURRENT_TILT_POSITION] == 0

    # Slat open
    mock_publish_state.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: _ENTITY_ID_SLAT},
        blocking=True,
    )

    publish_state = _get_publish_state(mock_publish_state)
    assert publish_state.read_slat_position() == 50

    async_fire_mqtt_message(hass, _TOPIC_SLAT_STATE, _PAYLOAD_SLAT_STATE_OPENED)
    await hass.async_block_till_done()

    entity_state = hass.states.get(_ENTITY_ID_SLAT)
    assert entity_state.state == CoverState.OPEN
    assert entity_state.attributes[ATTR_CURRENT_TILT_POSITION] == 50

    # SLat position
    mock_publish_state.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: _ENTITY_ID_SLAT, ATTR_TILT_POSITION: 75},
        blocking=True,
    )

    publish_state = _get_publish_state(mock_publish_state)
    assert publish_state.read_slat_position() == 75

    async_fire_mqtt_message(hass, _TOPIC_SLAT_STATE, _PAYLOAD_SLAT_STATE_POSITION)
    await hass.async_block_till_done()

    entity_state = hass.states.get(_ENTITY_ID_SLAT)
    assert entity_state.state == CoverState.OPEN
    assert entity_state.attributes[ATTR_CURRENT_TILT_POSITION] == 75

    # Slat close
    mock_publish_state.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: _ENTITY_ID_SLAT},
        blocking=True,
    )

    publish_state = _get_publish_state(mock_publish_state)
    assert publish_state.read_slat_position() == 0

    async_fire_mqtt_message(hass, _TOPIC_SLAT_STATE, _PAYLOAD_SLAT_STATE_CLOSED)
    await hass.async_block_till_done()

    entity_state = hass.states.get(_ENTITY_ID_SLAT)
    assert entity_state.state == CoverState.CLOSED
    assert entity_state.attributes[ATTR_CURRENT_TILT_POSITION] == 0


def _get_publish_state(mock_publish_state: AsyncMock) -> QbusMqttShutterState:
    assert mock_publish_state.call_count == 1
    state = mock_publish_state.call_args.args[0]
    assert isinstance(state, QbusMqttShutterState)
    return state
