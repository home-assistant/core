"""Tests for the devolo Home Network buttons."""
import logging
from unittest.mock import AsyncMock, patch

from devolo_plc_api.exceptions.device import DevicePasswordProtected, DeviceUnavailable
import pytest

from homeassistant.components.button import DOMAIN as PLATFORM, SERVICE_PRESS
from homeassistant.components.devolo_home_network.const import DOMAIN, START_WPS
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import configure_integration
from .mock import MockDevice


@pytest.mark.usefixtures("mock_device")
async def test_button_setup(hass: HomeAssistant):
    """Test default setup of the button component."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{PLATFORM}.{device_name}_{START_WPS}") is not None

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_device")
@pytest.mark.freeze_time("2021-11-08 12:00:00+00:00")
async def test_start_wps(hass: HomeAssistant):
    """Test update firmware button."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_{START_WPS}"

    with patch(
        "devolo_plc_api.device_api.deviceapi.DeviceApi.async_start_wps",
        new=AsyncMock(return_value=True),
    ) as start_wps:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(state_key)
        assert state is not None
        assert state.state == STATE_UNKNOWN

        # Emulate button press
        await hass.services.async_call(
            PLATFORM,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: state_key},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get(state_key)
        assert state.state == "2021-11-08T12:00:00+00:00"
        assert start_wps.call_count == 1

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("mock_device")
@pytest.mark.parametrize(
    "name, trigger_method",
    [[START_WPS, "async_start_wps"]],
)
async def test_device_failure(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    name: str,
    trigger_method: str,
):
    """Test device failure."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_{START_WPS}"

    with patch(
        f"devolo_plc_api.device_api.deviceapi.DeviceApi.{trigger_method}",
        side_effect=DeviceUnavailable,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Emulate button press
        await hass.services.async_call(
            PLATFORM,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: state_key},
            blocking=True,
        )
        await hass.async_block_till_done()

        assert caplog.records[-1].funcName == "async_press"
        assert caplog.records[-1].levelno == logging.ERROR
        assert caplog.records[-1].msg == "Device %s did not respond"

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    "name, set_method",
    [
        [START_WPS, "async_start_wps"],
    ],
)
async def test_auth_failed(
    hass: HomeAssistant, mock_device: MockDevice, name: str, set_method: str
):
    """Test setting unautherized triggers the reauth flow."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_{name}"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None

    setattr(mock_device.device, set_method, AsyncMock())
    api = getattr(mock_device.device, set_method)
    api.side_effect = DevicePasswordProtected

    await hass.services.async_call(
        PLATFORM,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: state_key},
        blocking=True,
    )
    await hass.async_block_till_done()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert "context" in flow
    assert flow["context"]["source"] == SOURCE_REAUTH
    assert flow["context"]["entry_id"] == entry.entry_id

    await hass.config_entries.async_unload(entry.entry_id)
