"""Tests for Switcher button platform."""
from unittest.mock import ANY, patch

from aioswitcher.api import DeviceState, SwitcherBaseResponse, ThermostatSwing
import pytest

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import slugify

from . import init_integration
from .consts import DUMMY_THERMOSTAT_DEVICE as DEVICE

BASE_ENTITY_ID = f"{BUTTON_DOMAIN}.{slugify(DEVICE.name)}"
ASSUME_ON_EID = BASE_ENTITY_ID + "_assume_on"
ASSUME_OFF_EID = BASE_ENTITY_ID + "_assume_off"
SWING_ON_EID = BASE_ENTITY_ID + "_vertical_swing_on"
SWING_OFF_EID = BASE_ENTITY_ID + "_vertical_swing_off"


@pytest.mark.parametrize("mock_bridge", [[DEVICE]], indirect=True)
async def test_assume_button(hass: HomeAssistant, mock_bridge, mock_api):
    """Test assume on/off button."""
    await init_integration(hass)
    assert mock_bridge

    assert hass.states.get(ASSUME_ON_EID) is not None
    assert hass.states.get(ASSUME_OFF_EID) is not None
    assert hass.states.get(SWING_ON_EID) is None
    assert hass.states.get(SWING_OFF_EID) is None

    with patch(
        "homeassistant.components.switcher_kis.climate.SwitcherType2Api.control_breeze_device",
    ) as mock_control_device:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ASSUME_ON_EID},
            blocking=True,
        )
        assert mock_api.call_count == 2
        mock_control_device.assert_called_once_with(
            ANY, state=DeviceState.ON, update_state=True
        )

        mock_control_device.reset_mock()
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: ASSUME_OFF_EID},
            blocking=True,
        )
        assert mock_api.call_count == 4
        mock_control_device.assert_called_once_with(
            ANY, state=DeviceState.OFF, update_state=True
        )


@pytest.mark.parametrize("mock_bridge", [[DEVICE]], indirect=True)
async def test_swing_button(hass: HomeAssistant, mock_bridge, mock_api, monkeypatch):
    """Test vertical swing on/off button."""
    monkeypatch.setattr(DEVICE, "remote_id", "ELEC7022")
    await init_integration(hass)
    assert mock_bridge

    assert hass.states.get(ASSUME_ON_EID) is None
    assert hass.states.get(ASSUME_OFF_EID) is None
    assert hass.states.get(SWING_ON_EID) is not None
    assert hass.states.get(SWING_OFF_EID) is not None

    with patch(
        "homeassistant.components.switcher_kis.climate.SwitcherType2Api.control_breeze_device",
    ) as mock_control_device:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: SWING_ON_EID},
            blocking=True,
        )
        assert mock_api.call_count == 2
        mock_control_device.assert_called_once_with(ANY, swing=ThermostatSwing.ON)

        mock_control_device.reset_mock()
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: SWING_OFF_EID},
            blocking=True,
        )
        assert mock_api.call_count == 4
        mock_control_device.assert_called_once_with(ANY, swing=ThermostatSwing.OFF)


@pytest.mark.parametrize("mock_bridge", [[DEVICE]], indirect=True)
async def test_control_device_fail(hass, mock_bridge, mock_api, monkeypatch):
    """Test control device fail."""
    await init_integration(hass)
    assert mock_bridge

    assert hass.states.get(ASSUME_ON_EID) is not None

    # Test exception during set hvac mode
    with patch(
        "homeassistant.components.switcher_kis.climate.SwitcherType2Api.control_breeze_device",
        side_effect=RuntimeError("fake error"),
    ) as mock_control_device:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                BUTTON_DOMAIN,
                SERVICE_PRESS,
                {ATTR_ENTITY_ID: ASSUME_ON_EID},
                blocking=True,
            )

        assert mock_api.call_count == 2
        mock_control_device.assert_called_once_with(
            ANY, state=DeviceState.ON, update_state=True
        )

        state = hass.states.get(ASSUME_ON_EID)
        assert state.state == STATE_UNAVAILABLE

    # Make device available again
    mock_bridge.mock_callbacks([DEVICE])
    await hass.async_block_till_done()

    assert hass.states.get(ASSUME_ON_EID) is not None

    # Test error response during turn on
    with patch(
        "homeassistant.components.switcher_kis.climate.SwitcherType2Api.control_breeze_device",
        return_value=SwitcherBaseResponse(None),
    ) as mock_control_device:
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                BUTTON_DOMAIN,
                SERVICE_PRESS,
                {ATTR_ENTITY_ID: ASSUME_ON_EID},
                blocking=True,
            )

        assert mock_api.call_count == 4
        mock_control_device.assert_called_once_with(
            ANY, state=DeviceState.ON, update_state=True
        )

        state = hass.states.get(ASSUME_ON_EID)
        assert state.state == STATE_UNAVAILABLE
