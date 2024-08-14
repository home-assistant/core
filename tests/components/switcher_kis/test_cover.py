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
    STATE_CLOSED,
    STATE_CLOSING,
    STATE_OPEN,
    STATE_OPENING,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import slugify

from . import init_integration
from .consts import (
    DUMMY_SHUTTER_DEVICE as DEVICE,
    DUMMY_SINGLE_SHUTTER_DUAL_DEVICE as DEVICE2,
    DUMMY_TOKEN as TOKEN,
    DUMMY_USERNAME as USERNAME,
)

ENTITY_ID = f"{COVER_DOMAIN}.{slugify(DEVICE.name)}"
ENTITY_ID2 = f"{COVER_DOMAIN}.{slugify(DEVICE2.name)}"


@pytest.mark.parametrize("mock_bridge", [[DEVICE]], indirect=True)
async def test_cover(
    hass: HomeAssistant, mock_bridge, mock_api, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test cover services."""
    await init_integration(hass)
    assert mock_bridge

    # Test initial state - open
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OPEN

    # Test set position
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherType2Api.set_position"
    ) as mock_control_device:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POSITION: 77},
            blocking=True,
        )

        monkeypatch.setattr(DEVICE, "position", 77)
        mock_bridge.mock_callbacks([DEVICE])
        await hass.async_block_till_done()

        assert mock_api.call_count == 2
        mock_control_device.assert_called_once_with(77, 0)
        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_OPEN
        assert state.attributes[ATTR_CURRENT_POSITION] == 77

    # Test open
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherType2Api.set_position"
    ) as mock_control_device:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

        monkeypatch.setattr(DEVICE, "direction", ShutterDirection.SHUTTER_UP)
        mock_bridge.mock_callbacks([DEVICE])
        await hass.async_block_till_done()

        assert mock_api.call_count == 4
        mock_control_device.assert_called_once_with(100, 0)
        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_OPENING

    # Test close
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherType2Api.set_position"
    ) as mock_control_device:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

        monkeypatch.setattr(DEVICE, "direction", ShutterDirection.SHUTTER_DOWN)
        mock_bridge.mock_callbacks([DEVICE])
        await hass.async_block_till_done()

        assert mock_api.call_count == 6
        mock_control_device.assert_called_once_with(0, 0)
        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_CLOSING

    # Test stop
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherType2Api.stop_shutter"
    ) as mock_control_device:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

        monkeypatch.setattr(DEVICE, "direction", ShutterDirection.SHUTTER_STOP)
        mock_bridge.mock_callbacks([DEVICE])
        await hass.async_block_till_done()

        assert mock_api.call_count == 8
        mock_control_device.assert_called_once_with(0)
        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_OPEN

    # Test closed on position == 0
    monkeypatch.setattr(DEVICE, "position", 0)
    mock_bridge.mock_callbacks([DEVICE])
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0


@pytest.mark.parametrize("mock_bridge", [[DEVICE]], indirect=True)
async def test_cover_control_fail(hass: HomeAssistant, mock_bridge, mock_api) -> None:
    """Test cover control fail."""
    await init_integration(hass)
    assert mock_bridge

    # Test initial state - open
    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OPEN

    # Test exception during set position
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherType2Api.set_position",
        side_effect=RuntimeError("fake error"),
    ) as mock_control_device:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                COVER_DOMAIN,
                SERVICE_SET_COVER_POSITION,
                {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POSITION: 44},
                blocking=True,
            )

        assert mock_api.call_count == 2
        mock_control_device.assert_called_once_with(44, 0)
        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_UNAVAILABLE

    # Make device available again
    mock_bridge.mock_callbacks([DEVICE])
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OPEN

    # Test error response during set position
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherType2Api.set_position",
        return_value=SwitcherBaseResponse(None),
    ) as mock_control_device:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                COVER_DOMAIN,
                SERVICE_SET_COVER_POSITION,
                {ATTR_ENTITY_ID: ENTITY_ID, ATTR_POSITION: 27},
                blocking=True,
            )

        assert mock_api.call_count == 4
        mock_control_device.assert_called_once_with(27, 0)
        state = hass.states.get(ENTITY_ID)
        assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("mock_bridge", [[DEVICE2]], indirect=True)
async def test_cover2(
    hass: HomeAssistant, mock_bridge, mock_api, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test cover services."""
    await init_integration(hass, USERNAME, TOKEN)
    assert mock_bridge

    # Test initial state - open
    state = hass.states.get(ENTITY_ID2)
    assert state.state == STATE_OPEN

    # Test set position
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherType2Api.set_position"
    ) as mock_control_device:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_SET_COVER_POSITION,
            {ATTR_ENTITY_ID: ENTITY_ID2, ATTR_POSITION: 77},
            blocking=True,
        )

        monkeypatch.setattr(DEVICE2, "position", 77)
        mock_bridge.mock_callbacks([DEVICE2])
        await hass.async_block_till_done()

        assert mock_api.call_count == 2
        mock_control_device.assert_called_once_with(77, 0)
        state = hass.states.get(ENTITY_ID2)
        assert state.state == STATE_OPEN
        assert state.attributes[ATTR_CURRENT_POSITION] == 77

    #     # Test open
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherType2Api.set_position"
    ) as mock_control_device:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: ENTITY_ID2},
            blocking=True,
        )

        monkeypatch.setattr(DEVICE2, "direction", ShutterDirection.SHUTTER_UP)
        mock_bridge.mock_callbacks([DEVICE2])
        await hass.async_block_till_done()

        assert mock_api.call_count == 4
        mock_control_device.assert_called_once_with(100, 0)
        state = hass.states.get(ENTITY_ID2)
        assert state.state == STATE_OPENING

    #     # Test close
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherType2Api.set_position"
    ) as mock_control_device:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: ENTITY_ID2},
            blocking=True,
        )

        monkeypatch.setattr(DEVICE2, "direction", ShutterDirection.SHUTTER_DOWN)
        mock_bridge.mock_callbacks([DEVICE2])
        await hass.async_block_till_done()

        assert mock_api.call_count == 6
        mock_control_device.assert_called_once_with(0, 0)
        state = hass.states.get(ENTITY_ID2)
        assert state.state == STATE_CLOSING

    #     # Test stop
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherType2Api.stop_shutter"
    ) as mock_control_device:
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_STOP_COVER,
            {ATTR_ENTITY_ID: ENTITY_ID2},
            blocking=True,
        )

        monkeypatch.setattr(DEVICE2, "direction", ShutterDirection.SHUTTER_STOP)
        mock_bridge.mock_callbacks([DEVICE2])
        await hass.async_block_till_done()

        assert mock_api.call_count == 8
        mock_control_device.assert_called_once_with(0)
        state = hass.states.get(ENTITY_ID2)
        assert state.state == STATE_OPEN

    # Test closed on position == 0
    monkeypatch.setattr(DEVICE2, "position", 0)
    mock_bridge.mock_callbacks([DEVICE2])
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID2)
    assert state.state == STATE_CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0


@pytest.mark.parametrize("mock_bridge", [[DEVICE2]], indirect=True)
async def test_cover_control_fail2(hass: HomeAssistant, mock_bridge, mock_api) -> None:
    """Test cover control fail."""
    await init_integration(hass, USERNAME, TOKEN)
    assert mock_bridge

    # Test initial state - open
    state = hass.states.get(ENTITY_ID2)
    assert state.state == STATE_OPEN

    # Test exception during set position
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherType2Api.set_position",
        side_effect=RuntimeError("fake error"),
    ) as mock_control_device:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                COVER_DOMAIN,
                SERVICE_SET_COVER_POSITION,
                {ATTR_ENTITY_ID: ENTITY_ID2, ATTR_POSITION: 44},
                blocking=True,
            )

        assert mock_api.call_count == 2
        mock_control_device.assert_called_once_with(44, 0)
        state = hass.states.get(ENTITY_ID2)
        assert state.state == STATE_UNAVAILABLE

    # Make device available again
    mock_bridge.mock_callbacks([DEVICE2])
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID2)
    assert state.state == STATE_OPEN

    # Test error response during set position
    with patch(
        "homeassistant.components.switcher_kis.cover.SwitcherType2Api.set_position",
        return_value=SwitcherBaseResponse(None),
    ) as mock_control_device:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                COVER_DOMAIN,
                SERVICE_SET_COVER_POSITION,
                {ATTR_ENTITY_ID: ENTITY_ID2, ATTR_POSITION: 27},
                blocking=True,
            )

        assert mock_api.call_count == 4
        mock_control_device.assert_called_once_with(27, 0)
        state = hass.states.get(ENTITY_ID2)
        assert state.state == STATE_UNAVAILABLE
