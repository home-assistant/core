"""Test the Z-Wave JS cover platform."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock

import pytest
from zwave_js_server.const import (
    CURRENT_STATE_PROPERTY,
    CURRENT_VALUE_PROPERTY,
    CommandClass,
    SetValueStatus,
)
from zwave_js_server.event import Event
from zwave_js_server.model.node import Node

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    CoverDeviceClass,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.components.zwave_js.const import LOGGER
from homeassistant.components.zwave_js.helpers import ZwaveValueMatcher
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant

from .common import replace_value_of_zwave_value

from tests.common import MockConfigEntry

WINDOW_COVER_ENTITY = "cover.zws_12"
GDC_COVER_ENTITY = "cover.aeon_labs_garage_door_controller_gen5"
BLIND_COVER_ENTITY = "cover.window_blind_controller"
SHUTTER_COVER_ENTITY = "cover.flush_shutter"
AEOTEC_SHUTTER_COVER_ENTITY = "cover.nano_shutter_v_3"
FIBARO_FGR_222_SHUTTER_COVER_ENTITY = "cover.fgr_222_test_cover"
FIBARO_FGR_223_SHUTTER_COVER_ENTITY = "cover.fgr_223_test_cover"
SHELLY_WAVE_SHUTTER_COVER_ENTITY = "cover.shelly_fw_14_2_0_test_cover"
LOGGER.setLevel(logging.DEBUG)


@pytest.fixture
def platforms() -> list[str]:
    """Fixture to specify platforms to test."""
    return [Platform.COVER]


async def test_window_cover(
    hass: HomeAssistant,
    client: MagicMock,
    chain_actuator_zws12: Node,
    integration: MockConfigEntry,
) -> None:
    """Test the cover entity."""
    node = chain_actuator_zws12
    state = hass.states.get(WINDOW_COVER_ENTITY)

    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.WINDOW

    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    # Test setting position
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: WINDOW_COVER_ENTITY, ATTR_POSITION: 50},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 6
    assert args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"] == 50

    client.async_send_command.reset_mock()

    # Test setting position
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: WINDOW_COVER_ENTITY, ATTR_POSITION: 0},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 6
    assert args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"] == 0

    client.async_send_command.reset_mock()

    # Test opening
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: WINDOW_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 6
    assert args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"]

    client.async_send_command.reset_mock()

    # Test stop after opening
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: WINDOW_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    open_args = client.async_send_command.call_args_list[0][0][0]
    assert open_args["command"] == "node.set_value"
    assert open_args["nodeId"] == 6
    assert open_args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "Open",
    }
    assert not open_args["value"]

    # Test position update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 6,
            "args": {
                "commandClassName": "Multilevel Switch",
                "commandClass": 38,
                "endpoint": 0,
                "property": "currentValue",
                "newValue": 99,
                "prevValue": 0,
                "propertyName": "currentValue",
            },
        },
    )
    node.receive_event(event)
    client.async_send_command.reset_mock()

    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state.state == CoverState.OPEN

    # Test closing
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: WINDOW_COVER_ENTITY},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 6
    assert args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"] == 0

    client.async_send_command.reset_mock()

    # Test stop after closing
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: WINDOW_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    open_args = client.async_send_command.call_args_list[0][0][0]
    assert open_args["command"] == "node.set_value"
    assert open_args["nodeId"] == 6
    assert open_args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "Open",
    }
    assert not open_args["value"]

    client.async_send_command.reset_mock()

    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 6,
            "args": {
                "commandClassName": "Multilevel Switch",
                "commandClass": 38,
                "endpoint": 0,
                "property": "currentValue",
                "newValue": 0,
                "prevValue": 0,
                "propertyName": "currentValue",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state.state == CoverState.CLOSED


async def test_fibaro_fgr222_shutter_cover(
    hass: HomeAssistant,
    client: MagicMock,
    fibaro_fgr222_shutter: Node,
    integration: MockConfigEntry,
) -> None:
    """Test tilt function of the Fibaro Shutter devices."""
    state = hass.states.get(FIBARO_FGR_222_SHUTTER_COVER_ENTITY)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.SHUTTER

    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0

    # Test opening tilts
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: FIBARO_FGR_222_SHUTTER_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 42
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 145,
        "property": "fibaro",
        "propertyKey": "venetianBlindsTilt",
    }
    assert args["value"] == 99

    client.async_send_command.reset_mock()

    # Test closing tilts
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: FIBARO_FGR_222_SHUTTER_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 42
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 145,
        "property": "fibaro",
        "propertyKey": "venetianBlindsTilt",
    }
    assert args["value"] == 0

    client.async_send_command.reset_mock()

    # Test setting tilt position
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: FIBARO_FGR_222_SHUTTER_COVER_ENTITY, ATTR_TILT_POSITION: 12},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 42
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 145,
        "property": "fibaro",
        "propertyKey": "venetianBlindsTilt",
    }
    assert args["value"] == 12

    # Test some tilt
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 42,
            "args": {
                "commandClassName": "Manufacturer Proprietary",
                "commandClass": 145,
                "endpoint": 0,
                "property": "fibaro",
                "propertyKey": "venetianBlindsTilt",
                "newValue": 99,
                "prevValue": 0,
                "propertyName": "fibaro",
                "propertyKeyName": "venetianBlindsTilt",
            },
        },
    )
    fibaro_fgr222_shutter.receive_event(event)
    state = hass.states.get(FIBARO_FGR_222_SHUTTER_COVER_ENTITY)
    assert state
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100


async def test_fibaro_fgr223_shutter_cover(
    hass: HomeAssistant,
    client: MagicMock,
    fibaro_fgr223_shutter: Node,
    integration: MockConfigEntry,
) -> None:
    """Test tilt function of the Fibaro Shutter devices."""
    state = hass.states.get(FIBARO_FGR_223_SHUTTER_COVER_ENTITY)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.SHUTTER

    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0

    # Test opening tilts
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: FIBARO_FGR_223_SHUTTER_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 10
    assert args["valueId"] == {
        "endpoint": 2,
        "commandClass": 38,
        "property": "targetValue",
    }
    assert args["value"] == 99

    client.async_send_command.reset_mock()
    # Test closing tilts
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: FIBARO_FGR_223_SHUTTER_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 10
    assert args["valueId"] == {
        "endpoint": 2,
        "commandClass": 38,
        "property": "targetValue",
    }
    assert args["value"] == 0

    client.async_send_command.reset_mock()
    # Test setting tilt position
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: FIBARO_FGR_223_SHUTTER_COVER_ENTITY, ATTR_TILT_POSITION: 12},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 10
    assert args["valueId"] == {
        "endpoint": 2,
        "commandClass": 38,
        "property": "targetValue",
    }
    assert args["value"] == 12

    # Test some tilt
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 10,
            "args": {
                "commandClassName": "Multilevel Switch",
                "commandClass": 38,
                "endpoint": 2,
                "property": "currentValue",
                "newValue": 99,
                "prevValue": 0,
                "propertyName": "currentValue",
            },
        },
    )
    fibaro_fgr223_shutter.receive_event(event)
    state = hass.states.get(FIBARO_FGR_223_SHUTTER_COVER_ENTITY)
    assert state
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100


async def test_shelly_wave_shutter_cover_with_tilt(
    hass: HomeAssistant,
    client: MagicMock,
    qubino_shutter_firmware_14_2_0: Node,
    integration: MockConfigEntry,
) -> None:
    """Test tilt function of the Shelly Wave Shutter with firmware 14.2.0.

    When parameter 71 is set to 1 (Venetian mode), endpoint 2 controls the tilt.
    """
    state = hass.states.get(SHELLY_WAVE_SHUTTER_COVER_ENTITY)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.SHUTTER

    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0

    # Test opening tilts
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: SHELLY_WAVE_SHUTTER_COVER_ENTITY},
        blocking=True,
    )

    assert client.async_send_command.call_count == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 5
    assert args["valueId"] == {
        "endpoint": 2,
        "commandClass": 38,
        "property": "targetValue",
    }
    assert args["value"] == 99

    client.async_send_command.reset_mock()

    # Test closing tilts
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: SHELLY_WAVE_SHUTTER_COVER_ENTITY},
        blocking=True,
    )

    assert client.async_send_command.call_count == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 5
    assert args["valueId"] == {
        "endpoint": 2,
        "commandClass": 38,
        "property": "targetValue",
    }
    assert args["value"] == 0

    client.async_send_command.reset_mock()

    # Test setting tilt position
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: SHELLY_WAVE_SHUTTER_COVER_ENTITY, ATTR_TILT_POSITION: 12},
        blocking=True,
    )

    assert client.async_send_command.call_count == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 5
    assert args["valueId"] == {
        "endpoint": 2,
        "commandClass": 38,
        "property": "targetValue",
    }
    assert args["value"] == 12

    # Test some tilt
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 5,
            "args": {
                "commandClassName": "Multilevel Switch",
                "commandClass": 38,
                "endpoint": 2,
                "property": "currentValue",
                "newValue": 99,
                "prevValue": 0,
                "propertyName": "currentValue",
            },
        },
    )
    qubino_shutter_firmware_14_2_0.receive_event(event)
    state = hass.states.get(SHELLY_WAVE_SHUTTER_COVER_ENTITY)
    assert state
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 100


async def test_aeotec_nano_shutter_cover(
    hass: HomeAssistant,
    client: MagicMock,
    aeotec_nano_shutter: Node,
    integration: MockConfigEntry,
) -> None:
    """Test movement of an Aeotec Nano Shutter cover entity. Useful to make sure the stop command logic is handled properly."""
    node = aeotec_nano_shutter
    state = hass.states.get(AEOTEC_SHUTTER_COVER_ENTITY)

    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.WINDOW

    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    # Test opening
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: AEOTEC_SHUTTER_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 3
    assert args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"]

    client.async_send_command.reset_mock()

    # Test stop after opening
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: AEOTEC_SHUTTER_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    open_args = client.async_send_command.call_args_list[0][0][0]
    assert open_args["command"] == "node.set_value"
    assert open_args["nodeId"] == 3
    assert open_args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "On",
    }
    assert not open_args["value"]

    # Test position update from value updated event
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 6,
            "args": {
                "commandClassName": "Multilevel Switch",
                "commandClass": 38,
                "endpoint": 0,
                "property": "currentValue",
                "newValue": 99,
                "prevValue": 0,
                "propertyName": "currentValue",
            },
        },
    )
    node.receive_event(event)

    client.async_send_command.reset_mock()

    state = hass.states.get(AEOTEC_SHUTTER_COVER_ENTITY)
    assert state.state == CoverState.OPEN

    # Test closing
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: AEOTEC_SHUTTER_COVER_ENTITY},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 3
    assert args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "targetValue",
    }
    assert args["value"] == 0

    client.async_send_command.reset_mock()

    # Test stop after closing
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: AEOTEC_SHUTTER_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    open_args = client.async_send_command.call_args_list[0][0][0]
    assert open_args["command"] == "node.set_value"
    assert open_args["nodeId"] == 3
    assert open_args["valueId"] == {
        "commandClass": 38,
        "endpoint": 0,
        "property": "On",
    }
    assert not open_args["value"]


async def test_blind_cover(
    hass: HomeAssistant,
    client: MagicMock,
    iblinds_v2: Node,
    integration: MockConfigEntry,
) -> None:
    """Test a blind cover entity."""
    state = hass.states.get(BLIND_COVER_ENTITY)

    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.BLIND


async def test_shutter_cover(
    hass: HomeAssistant,
    client: MagicMock,
    qubino_shutter: Node,
    integration: MockConfigEntry,
) -> None:
    """Test a shutter cover entity."""
    state = hass.states.get(SHUTTER_COVER_ENTITY)

    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.SHUTTER


async def test_motor_barrier_cover(
    hass: HomeAssistant,
    client: MagicMock,
    gdc_zw062: Node,
    integration: MockConfigEntry,
) -> None:
    """Test the cover entity."""
    node = gdc_zw062

    state = hass.states.get(GDC_COVER_ENTITY)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.GARAGE

    assert state.state == CoverState.CLOSED

    # Test open
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: GDC_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 12
    assert args["value"] == 255
    assert args["valueId"] == {
        "commandClass": 102,
        "endpoint": 0,
        "property": "targetState",
    }

    # state doesn't change until currentState value update is received
    state = hass.states.get(GDC_COVER_ENTITY)
    assert state.state == CoverState.CLOSED

    client.async_send_command.reset_mock()

    # Test close
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: GDC_COVER_ENTITY},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 12
    assert args["value"] == 0
    assert args["valueId"] == {
        "commandClass": 102,
        "endpoint": 0,
        "property": "targetState",
    }

    # state doesn't change until currentState value update is received
    state = hass.states.get(GDC_COVER_ENTITY)
    assert state.state == CoverState.CLOSED

    client.async_send_command.reset_mock()

    # Barrier sends an opening state
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 12,
            "args": {
                "commandClassName": "Barrier Operator",
                "commandClass": 102,
                "endpoint": 0,
                "property": "currentState",
                "newValue": 254,
                "prevValue": 0,
                "propertyName": "currentState",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(GDC_COVER_ENTITY)
    assert state.state == CoverState.OPENING

    # Barrier sends an opened state
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 12,
            "args": {
                "commandClassName": "Barrier Operator",
                "commandClass": 102,
                "endpoint": 0,
                "property": "currentState",
                "newValue": 255,
                "prevValue": 254,
                "propertyName": "currentState",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(GDC_COVER_ENTITY)
    assert state.state == CoverState.OPEN

    # Barrier sends a closing state
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 12,
            "args": {
                "commandClassName": "Barrier Operator",
                "commandClass": 102,
                "endpoint": 0,
                "property": "currentState",
                "newValue": 252,
                "prevValue": 255,
                "propertyName": "currentState",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(GDC_COVER_ENTITY)
    assert state.state == CoverState.CLOSING

    # Barrier sends a closed state
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 12,
            "args": {
                "commandClassName": "Barrier Operator",
                "commandClass": 102,
                "endpoint": 0,
                "property": "currentState",
                "newValue": 0,
                "prevValue": 252,
                "propertyName": "currentState",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(GDC_COVER_ENTITY)
    assert state.state == CoverState.CLOSED

    # Barrier sends a stopped state
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": 12,
            "args": {
                "commandClassName": "Barrier Operator",
                "commandClass": 102,
                "endpoint": 0,
                "property": "currentState",
                "newValue": 253,
                "prevValue": 252,
                "propertyName": "currentState",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(GDC_COVER_ENTITY)
    assert state.state == STATE_UNKNOWN


async def test_motor_barrier_cover_no_primary_value(
    hass: HomeAssistant,
    client: MagicMock,
    gdc_zw062_state: dict[str, Any],
    integration: MockConfigEntry,
) -> None:
    """Test the cover entity where primary value value is None."""
    node_state = replace_value_of_zwave_value(
        gdc_zw062_state,
        [
            ZwaveValueMatcher(
                property_=CURRENT_STATE_PROPERTY,
                command_class=CommandClass.BARRIER_OPERATOR,
            )
        ],
        None,
    )
    node = Node(client, node_state)
    client.driver.controller.emit("node added", {"node": node})
    await hass.async_block_till_done()

    state = hass.states.get(GDC_COVER_ENTITY)
    assert state
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.GARAGE

    assert state.state == STATE_UNKNOWN
    assert ATTR_CURRENT_POSITION not in state.attributes


async def test_fibaro_fgr222_shutter_cover_no_tilt(
    hass: HomeAssistant,
    client: MagicMock,
    fibaro_fgr222_shutter_state: dict[str, Any],
    integration: MockConfigEntry,
) -> None:
    """Test tilt function of the Fibaro Shutter devices with tilt value is None."""
    node_state = replace_value_of_zwave_value(
        fibaro_fgr222_shutter_state,
        [
            ZwaveValueMatcher(
                property_="fibaro",
                command_class=CommandClass.MANUFACTURER_PROPRIETARY,
                property_key="venetianBlindsTilt",
            ),
            ZwaveValueMatcher(
                property_=CURRENT_VALUE_PROPERTY,
                command_class=CommandClass.SWITCH_MULTILEVEL,
            ),
        ],
        None,
    )
    node = Node(client, node_state)
    client.driver.controller.emit("node added", {"node": node})
    await hass.async_block_till_done()

    state = hass.states.get(FIBARO_FGR_222_SHUTTER_COVER_ENTITY)
    assert state
    assert state.state == STATE_UNKNOWN
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes


async def test_fibaro_fgr223_shutter_cover_no_tilt(
    hass: HomeAssistant,
    client: MagicMock,
    fibaro_fgr223_shutter_state: dict[str, Any],
    integration: MockConfigEntry,
) -> None:
    """Test absence of tilt function for Fibaro Shutter roller blind.

    Fibaro Shutter devices can have operating mode set to roller blind (1).
    """
    node_state = replace_value_of_zwave_value(
        fibaro_fgr223_shutter_state,
        [
            ZwaveValueMatcher(
                property_=151,
                command_class=CommandClass.CONFIGURATION,
                endpoint=0,
            ),
        ],
        1,
    )
    node = Node(client, node_state)
    client.driver.controller.emit("node added", {"node": node})
    await hass.async_block_till_done()

    state = hass.states.get(FIBARO_FGR_223_SHUTTER_COVER_ENTITY)
    assert state
    assert state.state == CoverState.OPEN
    assert ATTR_CURRENT_POSITION in state.attributes
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes


async def test_iblinds_v3_cover(
    hass: HomeAssistant,
    client: MagicMock,
    iblinds_v3: Node,
    integration: MockConfigEntry,
) -> None:
    """Test iBlinds v3 cover which uses Window Covering CC."""
    entity_id = "cover.blind_west_bed_1_horizontal_slats_angle"
    state = hass.states.get(entity_id)
    assert state
    # This device has no state because there is no position value
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.SET_TILT_POSITION
        | CoverEntityFeature.STOP_TILT
    )
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert ATTR_CURRENT_TILT_POSITION in state.attributes
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 131
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 106,
        "property": "targetValue",
        "propertyKey": 23,
    }
    assert args["value"] == 0

    client.async_send_command.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 131
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 106,
        "property": "targetValue",
        "propertyKey": 23,
    }
    assert args["value"] == 50

    client.async_send_command.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: entity_id, ATTR_TILT_POSITION: 12},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 131
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 106,
        "property": "targetValue",
        "propertyKey": 23,
    }
    assert args["value"] == 12

    client.async_send_command.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER_TILT,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 131
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 106,
        "property": "levelChangeUp",
        "propertyKey": 23,
    }
    assert args["value"] is False

    client.async_send_command.reset_mock()


async def test_nice_ibt4zwave_cover(
    hass: HomeAssistant,
    client: MagicMock,
    nice_ibt4zwave: Node,
    integration: MockConfigEntry,
) -> None:
    """Test Nice IBT4ZWAVE cover."""
    entity_id = "cover.portail"
    state = hass.states.get(entity_id)
    assert state
    # This device has no state because there is no position value
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        CoverEntityFeature.CLOSE
        | CoverEntityFeature.OPEN
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.STOP
    )
    assert ATTR_CURRENT_POSITION in state.attributes
    assert state.attributes[ATTR_CURRENT_POSITION] == 0
    assert state.attributes[ATTR_DEVICE_CLASS] == CoverDeviceClass.GATE

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 72
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 38,
        "property": "targetValue",
    }
    assert args["value"] == 0

    client.async_send_command.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 72
    assert args["valueId"] == {
        "endpoint": 0,
        "commandClass": 38,
        "property": "targetValue",
    }
    assert args["value"] == 99

    client.async_send_command.reset_mock()


async def test_window_covering_open_close(
    hass: HomeAssistant,
    client: MagicMock,
    window_covering_outbound_bottom: Node,
    integration: MockConfigEntry,
) -> None:
    """Test Window Covering device open and close commands.

    A Window Covering device with position support
    should be able to open/close with the start/stop level change properties.
    """
    entity_id = "cover.node_2_outbound_bottom"
    state = hass.states.get(entity_id)

    # The entity has position support, but not tilt
    assert state
    assert ATTR_CURRENT_POSITION in state.attributes
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes

    # Test opening
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 2
    assert args["valueId"] == {
        "commandClass": 106,
        "endpoint": 0,
        "property": "levelChangeUp",
        "propertyKey": 13,
    }
    assert args["value"] is True

    client.async_send_command.reset_mock()

    # Test stop after opening
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 2
    assert args["valueId"] == {
        "commandClass": 106,
        "endpoint": 0,
        "property": "levelChangeUp",
        "propertyKey": 13,
    }
    assert args["value"] is False

    client.async_send_command.reset_mock()

    # Test closing
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 2
    assert args["valueId"] == {
        "commandClass": 106,
        "endpoint": 0,
        "property": "levelChangeDown",
        "propertyKey": 13,
    }
    assert args["value"] is True

    client.async_send_command.reset_mock()

    # Test stop after closing
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(client.async_send_command.call_args_list) == 1
    args = client.async_send_command.call_args[0][0]
    assert args["command"] == "node.set_value"
    assert args["nodeId"] == 2
    assert args["valueId"] == {
        "commandClass": 106,
        "endpoint": 0,
        "property": "levelChangeUp",
        "propertyKey": 13,
    }
    assert args["value"] is False

    client.async_send_command.reset_mock()


async def test_multilevel_switch_cover_moving_state_working(
    hass: HomeAssistant,
    client: MagicMock,
    chain_actuator_zws12: Node,
    integration: MockConfigEntry,
) -> None:
    """Test opening state with Supervision WORKING on Multilevel Switch cover."""
    node = chain_actuator_zws12
    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state
    assert state.state == CoverState.CLOSED

    # Simulate Supervision WORKING response
    client.async_send_command.return_value = {
        "result": {"status": SetValueStatus.WORKING}
    }

    # Open cover - should set OPENING state
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: WINDOW_COVER_ENTITY},
        blocking=True,
    )

    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state.state == CoverState.OPENING

    # Simulate intermediate position update (still moving)
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Multilevel Switch",
                "commandClass": 38,
                "endpoint": 0,
                "property": "currentValue",
                "newValue": 50,
                "prevValue": 0,
                "propertyName": "currentValue",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state.state == CoverState.OPENING

    # Simulate targetValue update (driver sets this when command is sent)
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Multilevel Switch",
                "commandClass": 38,
                "endpoint": 0,
                "property": "targetValue",
                "newValue": 99,
                "prevValue": 0,
                "propertyName": "targetValue",
            },
        },
    )
    node.receive_event(event)

    # Simulate reaching target position
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Multilevel Switch",
                "commandClass": 38,
                "endpoint": 0,
                "property": "currentValue",
                "newValue": 99,
                "prevValue": 50,
                "propertyName": "currentValue",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state.state == CoverState.OPEN


async def test_multilevel_switch_cover_moving_state_closing(
    hass: HomeAssistant,
    client: MagicMock,
    chain_actuator_zws12: Node,
    integration: MockConfigEntry,
) -> None:
    """Test closing state with Supervision WORKING on Multilevel Switch cover."""
    node = chain_actuator_zws12

    # First set position to open
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Multilevel Switch",
                "commandClass": 38,
                "endpoint": 0,
                "property": "currentValue",
                "newValue": 99,
                "prevValue": 0,
                "propertyName": "currentValue",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state.state == CoverState.OPEN

    # Simulate Supervision WORKING response
    client.async_send_command.return_value = {
        "result": {"status": SetValueStatus.WORKING}
    }

    # Close cover - should set CLOSING state
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: WINDOW_COVER_ENTITY},
        blocking=True,
    )

    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state.state == CoverState.CLOSING


async def test_multilevel_switch_cover_moving_state_success_no_moving(
    hass: HomeAssistant,
    client: MagicMock,
    chain_actuator_zws12: Node,
    integration: MockConfigEntry,
) -> None:
    """Test that SUCCESS does not set moving state on Multilevel Switch cover."""
    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state
    assert state.state == CoverState.CLOSED

    # Default mock already returns status 255 (SUCCESS)

    # Open cover - SUCCESS means device already at target, no moving state
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: WINDOW_COVER_ENTITY},
        blocking=True,
    )

    state = hass.states.get(WINDOW_COVER_ENTITY)
    # State should still be CLOSED since no value update has been received
    # and SUCCESS means the command completed immediately
    assert state.state == CoverState.CLOSED


async def test_multilevel_switch_cover_moving_state_unsupervised(
    hass: HomeAssistant,
    client: MagicMock,
    chain_actuator_zws12: Node,
    integration: MockConfigEntry,
) -> None:
    """Test SUCCESS_UNSUPERVISED sets moving state on Multilevel Switch cover."""
    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state
    assert state.state == CoverState.CLOSED

    # Simulate SUCCESS_UNSUPERVISED response
    client.async_send_command.return_value = {
        "result": {"status": SetValueStatus.SUCCESS_UNSUPERVISED}
    }

    # Open cover - should set OPENING state optimistically
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: WINDOW_COVER_ENTITY},
        blocking=True,
    )

    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state.state == CoverState.OPENING


async def test_multilevel_switch_cover_moving_state_stop_clears(
    hass: HomeAssistant,
    client: MagicMock,
    chain_actuator_zws12: Node,
    integration: MockConfigEntry,
) -> None:
    """Test stop_cover clears moving state on Multilevel Switch cover."""
    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state
    assert state.state == CoverState.CLOSED

    # Simulate WORKING response
    client.async_send_command.return_value = {
        "result": {"status": SetValueStatus.WORKING}
    }

    # Open cover to set OPENING state
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: WINDOW_COVER_ENTITY},
        blocking=True,
    )

    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state.state == CoverState.OPENING

    # Reset to SUCCESS for stop command
    client.async_send_command.return_value = {
        "result": {"status": SetValueStatus.SUCCESS}
    }

    # Stop cover - should clear opening state
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: WINDOW_COVER_ENTITY},
        blocking=True,
    )

    state = hass.states.get(WINDOW_COVER_ENTITY)
    # Cover is still at position 0 (closed), so is_closed returns True
    assert state.state == CoverState.CLOSED


async def test_multilevel_switch_cover_moving_state_set_position(
    hass: HomeAssistant,
    client: MagicMock,
    chain_actuator_zws12: Node,
    integration: MockConfigEntry,
) -> None:
    """Test moving state direction with set_cover_position on Multilevel Switch cover."""
    node = chain_actuator_zws12

    # First set position to 50 (open)
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Multilevel Switch",
                "commandClass": 38,
                "endpoint": 0,
                "property": "currentValue",
                "newValue": 50,
                "prevValue": 0,
                "propertyName": "currentValue",
            },
        },
    )
    node.receive_event(event)

    # Simulate WORKING response
    client.async_send_command.return_value = {
        "result": {"status": SetValueStatus.WORKING}
    }

    # Set position to 20 (closing direction)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: WINDOW_COVER_ENTITY, ATTR_POSITION: 20},
        blocking=True,
    )

    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state.state == CoverState.CLOSING

    # Set position to 80 (opening direction)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: WINDOW_COVER_ENTITY, ATTR_POSITION: 80},
        blocking=True,
    )

    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state.state == CoverState.OPENING


async def test_window_covering_cover_moving_state(
    hass: HomeAssistant,
    client: MagicMock,
    window_covering_outbound_bottom: Node,
    integration: MockConfigEntry,
) -> None:
    """Test moving state for Window Covering CC (StartLevelChange commands)."""
    node = window_covering_outbound_bottom
    entity_id = "cover.node_2_outbound_bottom"
    state = hass.states.get(entity_id)
    assert state

    # Default mock returns SUCCESS (255). For StartLevelChange,
    # SUCCESS means the device started moving.

    # Open cover - should set OPENING state
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == CoverState.OPENING

    client.async_send_command.reset_mock()

    # Stop cover - should clear moving state
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state not in (CoverState.OPENING, CoverState.CLOSING)

    client.async_send_command.reset_mock()

    # Close cover - should set CLOSING state
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    state = hass.states.get(entity_id)
    assert state.state == CoverState.CLOSING

    # Simulate reaching target: currentValue matches targetValue
    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Window Covering",
                "commandClass": 106,
                "endpoint": 0,
                "property": "targetValue",
                "propertyKey": 13,
                "newValue": 0,
                "prevValue": 52,
                "propertyName": "targetValue",
            },
        },
    )
    node.receive_event(event)

    event = Event(
        type="value updated",
        data={
            "source": "node",
            "event": "value updated",
            "nodeId": node.node_id,
            "args": {
                "commandClassName": "Window Covering",
                "commandClass": 106,
                "endpoint": 0,
                "property": "currentValue",
                "propertyKey": 13,
                "newValue": 0,
                "prevValue": 52,
                "propertyName": "currentValue",
            },
        },
    )
    node.receive_event(event)

    state = hass.states.get(entity_id)
    assert state.state == CoverState.CLOSED


async def test_multilevel_switch_cover_moving_state_none_result(
    hass: HomeAssistant,
    client: MagicMock,
    chain_actuator_zws12: Node,
    integration: MockConfigEntry,
) -> None:
    """Test None result (node asleep) does not set moving state on Multilevel Switch cover."""
    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state
    assert state.state == CoverState.CLOSED

    # Simulate None result (node asleep/command queued).
    # When node.async_send_command returns None, async_set_value returns None.
    client.async_send_command.return_value = None

    # Open cover - should NOT set OPENING state since result is None
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: WINDOW_COVER_ENTITY},
        blocking=True,
    )

    state = hass.states.get(WINDOW_COVER_ENTITY)
    assert state.state == CoverState.CLOSED
