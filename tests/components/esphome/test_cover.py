"""Test ESPHome covers."""

from collections.abc import Awaitable, Callable
from unittest.mock import call

from aioesphomeapi import (
    APIClient,
    CoverInfo,
    CoverOperation,
    CoverState as ESPHomeCoverState,
    EntityInfo,
    EntityState,
    UserService,
)

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
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant

from .conftest import MockESPHomeDevice


async def test_cover_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a generic cover entity."""
    entity_info = [
        CoverInfo(
            object_id="mycover",
            key=1,
            name="my cover",
            unique_id="my_cover",
            supports_position=True,
            supports_tilt=True,
            supports_stop=True,
        )
    ]
    states = [
        ESPHomeCoverState(
            key=1,
            position=0.5,
            tilt=0.5,
            current_operation=CoverOperation.IS_OPENING,
        )
    ]
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("cover.test_mycover")
    assert state is not None
    assert state.state == CoverState.OPENING
    assert state.attributes[ATTR_CURRENT_POSITION] == 50
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 50

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: "cover.test_mycover"},
        blocking=True,
    )
    mock_client.cover_command.assert_has_calls([call(key=1, position=0.0)])
    mock_client.cover_command.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: "cover.test_mycover"},
        blocking=True,
    )
    mock_client.cover_command.assert_has_calls([call(key=1, position=1.0)])
    mock_client.cover_command.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: "cover.test_mycover", ATTR_POSITION: 50},
        blocking=True,
    )
    mock_client.cover_command.assert_has_calls([call(key=1, position=0.5)])
    mock_client.cover_command.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: "cover.test_mycover"},
        blocking=True,
    )
    mock_client.cover_command.assert_has_calls([call(key=1, stop=True)])
    mock_client.cover_command.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test_mycover"},
        blocking=True,
    )
    mock_client.cover_command.assert_has_calls([call(key=1, tilt=1.0)])
    mock_client.cover_command.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: "cover.test_mycover"},
        blocking=True,
    )
    mock_client.cover_command.assert_has_calls([call(key=1, tilt=0.0)])
    mock_client.cover_command.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: "cover.test_mycover", ATTR_TILT_POSITION: 50},
        blocking=True,
    )
    mock_client.cover_command.assert_has_calls([call(key=1, tilt=0.5)])
    mock_client.cover_command.reset_mock()

    mock_device.set_state(
        ESPHomeCoverState(key=1, position=0.0, current_operation=CoverOperation.IDLE)
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_mycover")
    assert state is not None
    assert state.state == CoverState.CLOSED

    mock_device.set_state(
        ESPHomeCoverState(
            key=1, position=0.5, current_operation=CoverOperation.IS_CLOSING
        )
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_mycover")
    assert state is not None
    assert state.state == CoverState.CLOSING

    mock_device.set_state(
        ESPHomeCoverState(key=1, position=1.0, current_operation=CoverOperation.IDLE)
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_mycover")
    assert state is not None
    assert state.state == CoverState.OPEN


async def test_cover_entity_without_position(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
) -> None:
    """Test a generic cover entity without position, tilt, or stop."""
    entity_info = [
        CoverInfo(
            object_id="mycover",
            key=1,
            name="my cover",
            unique_id="my_cover",
            supports_position=False,
            supports_tilt=False,
            supports_stop=False,
        )
    ]
    states = [
        ESPHomeCoverState(
            key=1,
            position=0.5,
            tilt=0.5,
            current_operation=CoverOperation.IS_OPENING,
        )
    ]
    user_service = []
    await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("cover.test_mycover")
    assert state is not None
    assert state.state == CoverState.OPENING
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes
    assert ATTR_CURRENT_POSITION not in state.attributes
