"""Test the services for the Switcher integration."""

from unittest.mock import patch

from aioswitcher.api import Command
from aioswitcher.device import DeviceState
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.switcher_kis.const import (
    CONF_AUTO_OFF,
    CONF_TIMER_MINUTES,
    DOMAIN,
    SERVICE_SET_AUTO_OFF_NAME,
    SERVICE_TURN_ON_WITH_TIMER_NAME,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import time_period_str
from homeassistant.util import slugify

from . import init_integration
from .consts import (
    DUMMY_AUTO_OFF_SET,
    DUMMY_PLUG_DEVICE,
    DUMMY_TIMER_MINUTES_SET,
    DUMMY_WATER_HEATER_DEVICE,
)


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_turn_on_with_timer_service(
    hass: HomeAssistant, mock_bridge, mock_api, monkeypatch
) -> None:
    """Test the turn on with timer service."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    # Test initial state - off
    monkeypatch.setattr(device, "device_state", DeviceState.OFF)
    mock_bridge.mock_callbacks([DUMMY_WATER_HEATER_DEVICE])
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    with patch(
        "homeassistant.components.switcher_kis.switch.SwitcherType1Api.control_device"
    ) as mock_control_device:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_TURN_ON_WITH_TIMER_NAME,
            {
                ATTR_ENTITY_ID: entity_id,
                CONF_TIMER_MINUTES: DUMMY_TIMER_MINUTES_SET,
            },
            blocking=True,
        )

        assert mock_api.call_count == 2
        mock_control_device.assert_called_once_with(
            Command.ON, int(DUMMY_TIMER_MINUTES_SET)
        )
        state = hass.states.get(entity_id)
        assert state.state == STATE_ON


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_set_auto_off_service(hass: HomeAssistant, mock_bridge, mock_api) -> None:
    """Test the set auto off service."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    with patch(
        "homeassistant.components.switcher_kis.switch.SwitcherType1Api.set_auto_shutdown"
    ) as mock_set_auto_shutdown:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_AUTO_OFF_NAME,
            {ATTR_ENTITY_ID: entity_id, CONF_AUTO_OFF: DUMMY_AUTO_OFF_SET},
            blocking=True,
        )

        assert mock_api.call_count == 2
        mock_set_auto_shutdown.assert_called_once_with(
            time_period_str(DUMMY_AUTO_OFF_SET)
        )


@pytest.mark.parametrize("mock_bridge", [[DUMMY_WATER_HEATER_DEVICE]], indirect=True)
async def test_set_auto_off_service_fail(
    hass: HomeAssistant, mock_bridge, mock_api, caplog: pytest.LogCaptureFixture
) -> None:
    """Test set auto off service failed."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_WATER_HEATER_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    with patch(
        "homeassistant.components.switcher_kis.switch.SwitcherType1Api.set_auto_shutdown",
        return_value=None,
    ) as mock_set_auto_shutdown:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_AUTO_OFF_NAME,
            {ATTR_ENTITY_ID: entity_id, CONF_AUTO_OFF: DUMMY_AUTO_OFF_SET},
            blocking=True,
        )

        assert mock_api.call_count == 2
        mock_set_auto_shutdown.assert_called_once_with(
            time_period_str(DUMMY_AUTO_OFF_SET)
        )
        assert (
            f"Call api for {device.name} failed, api: 'set_auto_shutdown'"
            in caplog.text
        )
        state = hass.states.get(entity_id)
        assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("mock_bridge", [[DUMMY_PLUG_DEVICE]], indirect=True)
async def test_plug_unsupported_services(
    hass: HomeAssistant, mock_bridge, mock_api, caplog: pytest.LogCaptureFixture
) -> None:
    """Test plug device unsupported services."""
    await init_integration(hass)
    assert mock_bridge

    device = DUMMY_PLUG_DEVICE
    entity_id = f"{SWITCH_DOMAIN}.{slugify(device.name)}"

    # Turn on with timer
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON_WITH_TIMER_NAME,
        {
            ATTR_ENTITY_ID: entity_id,
            CONF_TIMER_MINUTES: DUMMY_TIMER_MINUTES_SET,
        },
        blocking=True,
    )

    assert mock_api.call_count == 0
    assert (
        f"Service '{SERVICE_TURN_ON_WITH_TIMER_NAME}' is not supported by {device.name}"
        in caplog.text
    )

    # Auto off
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_AUTO_OFF_NAME,
        {ATTR_ENTITY_ID: entity_id, CONF_AUTO_OFF: DUMMY_AUTO_OFF_SET},
        blocking=True,
    )

    assert mock_api.call_count == 0
    assert (
        f"Service '{SERVICE_SET_AUTO_OFF_NAME}' is not supported by {device.name}"
        in caplog.text
    )
