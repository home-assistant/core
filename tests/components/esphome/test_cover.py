"""Test ESPHome covers."""

from unittest.mock import call

from aioesphomeapi import (
    APIClient,
    CoverInfo,
    CoverOperation,
    CoverState as ESPHomeCoverState,
)

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    CoverService,
    CoverServiceArgument,
    CoverState,
)
from homeassistant.const import TargetKey
from homeassistant.core import HomeAssistant

from .conftest import MockESPHomeDeviceType


async def test_cover_entity(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a generic cover entity."""
    entity_info = [
        CoverInfo(
            object_id="mycover",
            key=1,
            name="my cover",
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
    state = hass.states.get("cover.test_my_cover")
    assert state is not None
    assert state.state == CoverState.OPENING
    assert state.attributes[ATTR_CURRENT_POSITION] == 50
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 50

    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.CLOSE,
        {TargetKey.ENTITY_ID: "cover.test_my_cover"},
        blocking=True,
    )
    mock_client.cover_command.assert_has_calls([call(key=1, position=0.0, device_id=0)])
    mock_client.cover_command.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.OPEN,
        {TargetKey.ENTITY_ID: "cover.test_my_cover"},
        blocking=True,
    )
    mock_client.cover_command.assert_has_calls([call(key=1, position=1.0, device_id=0)])
    mock_client.cover_command.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.SET_POSITION,
        {TargetKey.ENTITY_ID: "cover.test_my_cover", CoverServiceArgument.POSITION: 50},
        blocking=True,
    )
    mock_client.cover_command.assert_has_calls([call(key=1, position=0.5, device_id=0)])
    mock_client.cover_command.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.STOP,
        {TargetKey.ENTITY_ID: "cover.test_my_cover"},
        blocking=True,
    )
    mock_client.cover_command.assert_has_calls([call(key=1, stop=True, device_id=0)])
    mock_client.cover_command.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.OPEN_TILT,
        {TargetKey.ENTITY_ID: "cover.test_my_cover"},
        blocking=True,
    )
    mock_client.cover_command.assert_has_calls([call(key=1, tilt=1.0, device_id=0)])
    mock_client.cover_command.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.CLOSE_TILT,
        {TargetKey.ENTITY_ID: "cover.test_my_cover"},
        blocking=True,
    )
    mock_client.cover_command.assert_has_calls([call(key=1, tilt=0.0, device_id=0)])
    mock_client.cover_command.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        CoverService.SET_TILT_POSITION,
        {
            TargetKey.ENTITY_ID: "cover.test_my_cover",
            CoverServiceArgument.TILT_POSITION: 50,
        },
        blocking=True,
    )
    mock_client.cover_command.assert_has_calls([call(key=1, tilt=0.5, device_id=0)])
    mock_client.cover_command.reset_mock()

    mock_device.set_state(
        ESPHomeCoverState(key=1, position=0.0, current_operation=CoverOperation.IDLE)
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_my_cover")
    assert state is not None
    assert state.state == CoverState.CLOSED

    mock_device.set_state(
        ESPHomeCoverState(
            key=1, position=0.5, current_operation=CoverOperation.IS_CLOSING
        )
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_my_cover")
    assert state is not None
    assert state.state == CoverState.CLOSING

    mock_device.set_state(
        ESPHomeCoverState(key=1, position=1.0, current_operation=CoverOperation.IDLE)
    )
    await hass.async_block_till_done()
    state = hass.states.get("cover.test_my_cover")
    assert state is not None
    assert state.state == CoverState.OPEN


async def test_cover_entity_without_position(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: MockESPHomeDeviceType,
) -> None:
    """Test a generic cover entity without position, tilt, or stop."""
    entity_info = [
        CoverInfo(
            object_id="mycover",
            key=1,
            name="my cover",
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
    state = hass.states.get("cover.test_my_cover")
    assert state is not None
    assert state.state == CoverState.OPENING
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes
    assert ATTR_CURRENT_POSITION not in state.attributes
