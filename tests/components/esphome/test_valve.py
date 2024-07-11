"""Test ESPHome valves."""

from collections.abc import Awaitable, Callable
from unittest.mock import call

from aioesphomeapi import (
    APIClient,
    EntityInfo,
    EntityState,
    UserService,
    ValveInfo,
    ValveOperation,
    ValveState,
)

from homeassistant.components.valve import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as VALVE_DOMAIN,
    SERVICE_CLOSE_VALVE,
    SERVICE_OPEN_VALVE,
    SERVICE_SET_VALVE_POSITION,
    SERVICE_STOP_VALVE,
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import MockESPHomeDevice


async def test_valve_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a generic valve entity."""
    entity_info = [
        ValveInfo(
            object_id="myvalve",
            key=1,
            name="my valve",
            unique_id="my_valve",
            supports_position=True,
            supports_stop=True,
        )
    ]
    states = [
        ValveState(
            key=1,
            position=0.5,
            current_operation=ValveOperation.IS_OPENING,
        )
    ]
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("valve.test_myvalve")
    assert state is not None
    assert state.state == STATE_OPENING
    assert state.attributes[ATTR_CURRENT_POSITION] == 50

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_CLOSE_VALVE,
        {ATTR_ENTITY_ID: "valve.test_myvalve"},
        blocking=True,
    )
    mock_client.valve_command.assert_has_calls([call(key=1, position=0.0)])
    mock_client.valve_command.reset_mock()

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_OPEN_VALVE,
        {ATTR_ENTITY_ID: "valve.test_myvalve"},
        blocking=True,
    )
    mock_client.valve_command.assert_has_calls([call(key=1, position=1.0)])
    mock_client.valve_command.reset_mock()

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_SET_VALVE_POSITION,
        {ATTR_ENTITY_ID: "valve.test_myvalve", ATTR_POSITION: 50},
        blocking=True,
    )
    mock_client.valve_command.assert_has_calls([call(key=1, position=0.5)])
    mock_client.valve_command.reset_mock()

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_STOP_VALVE,
        {ATTR_ENTITY_ID: "valve.test_myvalve"},
        blocking=True,
    )
    mock_client.valve_command.assert_has_calls([call(key=1, stop=True)])
    mock_client.valve_command.reset_mock()

    mock_device.set_state(
        ValveState(key=1, position=0.0, current_operation=ValveOperation.IDLE)
    )
    await hass.async_block_till_done()
    state = hass.states.get("valve.test_myvalve")
    assert state is not None
    assert state.state == STATE_CLOSED

    mock_device.set_state(
        ValveState(key=1, position=0.5, current_operation=ValveOperation.IS_CLOSING)
    )
    await hass.async_block_till_done()
    state = hass.states.get("valve.test_myvalve")
    assert state is not None
    assert state.state == STATE_CLOSING

    mock_device.set_state(
        ValveState(key=1, position=1.0, current_operation=ValveOperation.IDLE)
    )
    await hass.async_block_till_done()
    state = hass.states.get("valve.test_myvalve")
    assert state is not None
    assert state.state == STATE_OPEN


async def test_valve_entity_without_position(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a generic valve entity without position or stop."""
    entity_info = [
        ValveInfo(
            object_id="myvalve",
            key=1,
            name="my valve",
            unique_id="my_valve",
            supports_position=False,
            supports_stop=False,
        )
    ]
    states = [
        ValveState(
            key=1,
            position=0.5,
            current_operation=ValveOperation.IS_OPENING,
        )
    ]
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("valve.test_myvalve")
    assert state is not None
    assert state.state == STATE_OPENING
    assert ATTR_CURRENT_POSITION not in state.attributes

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_CLOSE_VALVE,
        {ATTR_ENTITY_ID: "valve.test_myvalve"},
        blocking=True,
    )
    mock_client.valve_command.assert_has_calls([call(key=1, position=0.0)])
    mock_client.valve_command.reset_mock()

    await hass.services.async_call(
        VALVE_DOMAIN,
        SERVICE_OPEN_VALVE,
        {ATTR_ENTITY_ID: "valve.test_myvalve"},
        blocking=True,
    )
    mock_client.valve_command.assert_has_calls([call(key=1, position=1.0)])
    mock_client.valve_command.reset_mock()

    mock_device.set_state(
        ValveState(key=1, position=0.0, current_operation=ValveOperation.IDLE)
    )
    await hass.async_block_till_done()
    state = hass.states.get("valve.test_myvalve")
    assert state is not None
    assert state.state == STATE_CLOSED
