"""Test the Switcher switch platform."""

from unittest.mock import patch

from aioswitcher.api import Command, ShutterChildLock, SwitcherBaseResponse
from aioswitcher.device import DeviceState
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import slugify

from . import init_integration
from .consts import (
    DUMMY_DUAL_SHUTTER_SINGLE_LIGHT_DEVICE as DEVICE3,
    DUMMY_PLUG_DEVICE,
    DUMMY_SHUTTER_DEVICE as DEVICE,
    DUMMY_SINGLE_SHUTTER_DUAL_LIGHT_DEVICE as DEVICE2,
    DUMMY_TOKEN as TOKEN,
    DUMMY_USERNAME as USERNAME,
    DUMMY_WATER_HEATER_DEVICE,
)

ENTITY_ID = f"{SWITCH_DOMAIN}.{slugify(DEVICE.name)}_child_lock"
ENTITY_ID2 = f"{SWITCH_DOMAIN}.{slugify(DEVICE2.name)}_child_lock"
ENTITY_ID3 = f"{SWITCH_DOMAIN}.{slugify(DEVICE3.name)}_child_lock_1"
ENTITY_ID3_2 = f"{SWITCH_DOMAIN}.{slugify(DEVICE3.name)}_child_lock_2"


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_switch(
    hass: HomeAssistant, mock_bridge, mock_api, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test the switch."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    # Test initial state - on
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    # Test state change on --> off
    monkeypatch.setattr(device, "device_state", DeviceState.OFF)
    mock_bridge.mock_callbacks([DUMMY_WATER_HEATER_DEVICE])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Test turning on
    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.control_device",
    ) as mock_control_device:
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        assert mock_api.call_count == 2
        mock_control_device.assert_called_once_with(Command.ON)
        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    # Test turning off
    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.control_device"
    ) as mock_control_device:
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        assert mock_api.call_count == 4
        mock_control_device.assert_called_once_with(Command.OFF)
        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF


@pytest.mark.parametrize("mock_bridge", [[DUMMY_PLUG_DEVICE]], indirect=True)
async def test_switch_control_fail(
    hass: HomeAssistant,
    mock_bridge,
    mock_api,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test switch control fail."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_PLUG_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    # Test initial state - off
    monkeypatch.setattr(device, "device_state", DeviceState.OFF)
    mock_bridge.mock_callbacks([DUMMY_PLUG_DEVICE])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Test exception during turn on
    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.control_device",
        side_effect=RuntimeError("fake error"),
    ) as mock_control_device:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )

        assert mock_api.call_count == 2
        mock_control_device.assert_called_once_with(Command.ON)
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE

    # Make device available again
    mock_bridge.mock_callbacks([DUMMY_PLUG_DEVICE])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Test error response during turn on
    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.control_device",
        return_value=SwitcherBaseResponse(None),
    ) as mock_control_device:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )

        assert mock_api.call_count == 4
        mock_control_device.assert_called_once_with(Command.ON)
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    (
        "device",
        "entity_id",
        "cover_id",
        "child_lock_state",
    ),
    [
        (
            DEVICE,
            ENTITY_ID,
            0,
            [ShutterChildLock.OFF],
        ),
        (
            DEVICE2,
            ENTITY_ID2,
            0,
            [ShutterChildLock.OFF],
        ),
        (
            DEVICE3,
            ENTITY_ID3,
            0,
            [ShutterChildLock.OFF, ShutterChildLock.ON],
        ),
        (
            DEVICE3,
            ENTITY_ID3_2,
            1,
            [ShutterChildLock.ON, ShutterChildLock.OFF],
        ),
    ],
)
@pytest.mark.parametrize("mock_bridge", [[DEVICE, DEVICE2, DEVICE3]], indirect=True)
async def test_child_lock_switch(
    hass: HomeAssistant,
    mock_bridge,
    mock_api,
    monkeypatch: pytest.MonkeyPatch,
    device,
    entity_id: str,
    cover_id: int,
    child_lock_state: list[ShutterChildLock],
) -> None:
    """Test the switch."""
    await init_integration(hass, USERNAME, TOKEN)
    assert mock_bridge

    # Test initial state - on
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    # Test state change on --> off
    monkeypatch.setattr(device, "child_lock", child_lock_state)
    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Test turning on child lock
    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.set_shutter_child_lock",
    ) as mock_control_device:
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        assert mock_api.call_count == 2
        mock_control_device.assert_called_once_with(ShutterChildLock.ON, cover_id)
        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    # Test turning off
    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.set_shutter_child_lock"
    ) as mock_control_device:
        await hass.services.async_call(
            SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )

        assert mock_api.call_count == 4
        mock_control_device.assert_called_once_with(ShutterChildLock.OFF, cover_id)
        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF


@pytest.mark.parametrize(
    (
        "device",
        "entity_id",
        "cover_id",
        "child_lock_state",
    ),
    [
        (
            DEVICE,
            ENTITY_ID,
            0,
            [ShutterChildLock.OFF],
        ),
        (
            DEVICE2,
            ENTITY_ID2,
            0,
            [ShutterChildLock.OFF],
        ),
        (
            DEVICE3,
            ENTITY_ID3,
            0,
            [ShutterChildLock.OFF, ShutterChildLock.ON],
        ),
        (
            DEVICE3,
            ENTITY_ID3_2,
            1,
            [ShutterChildLock.ON, ShutterChildLock.OFF],
        ),
    ],
)
@pytest.mark.parametrize("mock_bridge", [[DEVICE, DEVICE2, DEVICE3]], indirect=True)
async def test_child_lock_control_fail(
    hass: HomeAssistant,
    mock_bridge,
    mock_api,
    monkeypatch: pytest.MonkeyPatch,
    device,
    entity_id: str,
    cover_id: int,
    child_lock_state: list[ShutterChildLock],
) -> None:
    """Test switch control fail."""
    await init_integration(hass, USERNAME, TOKEN)
    assert mock_bridge

    # Test initial state - off
    monkeypatch.setattr(device, "child_lock", child_lock_state)
    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Test exception during turn on
    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.set_shutter_child_lock",
        side_effect=RuntimeError("fake error"),
    ) as mock_control_device:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )

        assert mock_api.call_count == 2
        mock_control_device.assert_called_once_with(ShutterChildLock.ON, cover_id)
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE

    # Make device available again
    mock_bridge.mock_callbacks([device])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    # Test error response during turn on
    with patch(
        "homeassistant.components.switcher_kis.entity.SwitcherApi.set_shutter_child_lock",
        return_value=SwitcherBaseResponse(None),
    ) as mock_control_device:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                SWITCH_DOMAIN,
                SERVICE_TURN_ON,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )

        assert mock_api.call_count == 4
        mock_control_device.assert_called_once_with(ShutterChildLock.ON, cover_id)
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE
