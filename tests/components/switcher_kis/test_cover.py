"""Test the Switcher cover platform."""

from unittest.mock import patch

from aioswitcher.api import SwitcherBaseResponse
from aioswitcher.device import ShutterDirection
import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    SERVICE_STOP_COVER,
    CoverState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import slugify

from . import init_integration
from .consts import (
    DUMMY_DUAL_SHUTTER_SINGLE_LIGHT_DEVICE as DEVICE3,
    DUMMY_SHUTTER_DEVICE as DEVICE,
    DUMMY_SINGLE_SHUTTER_DUAL_LIGHT_DEVICE as DEVICE2,
    DUMMY_TOKEN as TOKEN,
    DUMMY_USERNAME as USERNAME,
)

ENTITY_ID = f"{COVER_DOMAIN}.{slugify(DEVICE.name)}"
ENTITY_ID2 = f"{COVER_DOMAIN}.{slugify(DEVICE2.name)}"
ENTITY_ID3 = f"{COVER_DOMAIN}.{slugify(DEVICE3.name)}_cover_1"
ENTITY_ID3_2 = f"{COVER_DOMAIN}.{slugify(DEVICE3.name)}_cover_2"


@pytest.mark.parametrize(
    (
        "device",
        "entity_id",
        "cover_id",
        "position_open",
        "position_close",
        "direction_open",
        "direction_close",
        "direction_stop",
    ),
    [
        (
            DEVICE,
            ENTITY_ID,
            0,
            [77],
            [0],
            [ShutterDirection.SHUTTER_UP],
            [ShutterDirection.SHUTTER_DOWN],
            [ShutterDirection.SHUTTER_STOP],
        ),
        (
            DEVICE2,
            ENTITY_ID2,
            0,
            [77],
            [0],
            [ShutterDirection.SHUTTER_UP],
            [ShutterDirection.SHUTTER_DOWN],
            [ShutterDirection.SHUTTER_STOP],
        ),
        (
            DEVICE3,
            ENTITY_ID3,
            0,
            [77, 0],
            [0, 0],
            [ShutterDirection.SHUTTER_UP, ShutterDirection.SHUTTER_STOP],
            [ShutterDirection.SHUTTER_DOWN, ShutterDirection.SHUTTER_STOP],
            [ShutterDirection.SHUTTER_STOP, ShutterDirection.SHUTTER_STOP],
        ),
        (
            DEVICE3,
            ENTITY_ID3_2,
            1,
            [0, 77],
            [0, 0],
            [ShutterDirection.SHUTTER_STOP, ShutterDirection.SHUTTER_UP],
            [ShutterDirection.SHUTTER_STOP, ShutterDirection.SHUTTER_DOWN],
            [ShutterDirection.SHUTTER_STOP, ShutterDirection.SHUTTER_STOP],
        ),
    ],
)
@pytest.mark.parametrize("mock_bridge", [[DEVICE, DEVICE2, DEVICE3]], indirect=True)
async def test_cover(
    hass: HomeAssistant,
    mock_bridge,
    mock_api,
    monkeypatch: pytest.MonkeyPatch,
    device,
    entity_id: str,
    cover_id: int,
    position_open: list[int],
    position_close: list[int],
    direction_open: list[ShutterDirection],
    direction_close: list[ShutterDirection],
    direction_stop: list[ShutterDirection],
) -> None:
    """Test cover services."""
    await init_integration(hass, USERNAME, TOKEN)
    assert mock_bridge

    # Test initial state - open
    state = hass.states.get(entity_id)
    assert state.state == CoverState.OPEN

    # Test set position
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherApi.set_position"
    ) as mock_control_device:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 77},
            blocking=True,
        )

        monkeypatch.setattr(device, "position", position_open)
        mock_bridge.mock_callbacks([device])
        await hass.async_block_till_done()

        assert mock_api.call_count == 2
        mock_control_device.assert_called_once_with(77, cover_id)
        state = hass.states.get(entity_id)
        assert state.state == CoverState.OPEN
        assert state.attributes[ATTR_CURRENT_POSITION] == 77

    # Test open
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherApi.set_position"
    ) as mock_control_device:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        monkeypatch.setattr(device, "direction", direction_open)
        mock_bridge.mock_callbacks([device])
        await hass.async_block_till_done()

        assert mock_api.call_count == 4
        mock_control_device.assert_called_once_with(100, cover_id)
        state = hass.states.get(entity_id)
        assert state.state == CoverState.OPENING

    # Test close
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherApi.set_position"
    ) as mock_control_device:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        monkeypatch.setattr(device, "direction", direction_close)
        mock_bridge.mock_callbacks([device])
        await hass.async_block_till_done()

        assert mock_api.call_count == 6
        mock_control_device.assert_called_once_with(0, cover_id)
        state = hass.states.get(entity_id)
        assert state.state == CoverState.CLOSING

    # Test stop
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherApi.stop_shutter"
    ) as mock_control_device:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        monkeypatch.setattr(device, "direction", direction_stop)
        mock_bridge.mock_callbacks([device])
        await hass.async_block_till_done()

        assert mock_api.call_count == 8
        mock_control_device.assert_called_once_with(cover_id)
        state = hass.states.get(entity_id)
        assert state.state == CoverState.OPEN

    # Test closed on position == 0
    monkeypatch.setattr(device, "position", position_close)
    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0


@pytest.mark.parametrize(
    ("device", "entity_id", "cover_id"),
    [
        (DEVICE, ENTITY_ID, 0),
        (DEVICE2, ENTITY_ID2, 0),
        (DEVICE3, ENTITY_ID3, 0),
        (DEVICE3, ENTITY_ID3_2, 1),
    ],
)
@pytest.mark.parametrize("mock_bridge", [[DEVICE, DEVICE2, DEVICE3]], indirect=True)
async def test_cover_control_fail(
    hass: HomeAssistant,
    mock_bridge,
    mock_api,
    device,
    entity_id: str,
    cover_id: int,
) -> None:
    """Test cover control fail."""
    await init_integration(hass, USERNAME, TOKEN)
    assert mock_bridge

    # Test initial state - open
    state = hass.states.get(entity_id)
    assert state.state == CoverState.OPEN

    # Test exception during set position
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherApi.set_position",
        side_effect=RuntimeError("fake error"),
    ) as mock_control_device:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                COVER_DOMAIN,
                SERVICE_SET_COVER_POSITION,
                {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 44},
                blocking=True,
            )

        assert mock_api.call_count == 2
        mock_control_device.assert_called_once_with(44, cover_id)
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE

    # Make device available again
    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == CoverState.OPEN

    # Test error response during set position
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherApi.set_position",
        return_value=SwitcherBaseResponse(None),
    ) as mock_control_device:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                COVER_DOMAIN,
                SERVICE_SET_COVER_POSITION,
                {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 27},
                blocking=True,
            )

        assert mock_api.call_count == 4
        mock_control_device.assert_called_once_with(27, cover_id)
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("mock_bridge", [[DEVICE2, DEVICE3]], indirect=True)
async def test_cover2_no_token(
    hass: HomeAssistant, mock_bridge, mock_api, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test cover with token needed without token specified."""
    await init_integration(hass)
    assert mock_bridge

    assert mock_api.call_count == 0
