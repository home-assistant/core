"""Tests for the devolo Home Network buttons."""
from unittest.mock import AsyncMock

from devolo_plc_api.exceptions.device import DevicePasswordProtected, DeviceUnavailable
import pytest

from homeassistant.components.button import (
    DOMAIN as PLATFORM,
    SERVICE_PRESS,
    ButtonDeviceClass,
)
from homeassistant.components.devolo_home_network.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory

from . import configure_integration
from .mock import MockDevice


@pytest.mark.usefixtures("mock_device")
async def test_button_setup(hass: HomeAssistant) -> None:
    """Test default setup of the button component."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (
        hass.states.get(f"{PLATFORM}.{device_name}_identify_device_with_a_blinking_led")
        is not None
    )
    assert hass.states.get(f"{PLATFORM}.{device_name}_start_plc_pairing") is not None
    assert hass.states.get(f"{PLATFORM}.{device_name}_restart_device") is not None
    assert hass.states.get(f"{PLATFORM}.{device_name}_start_wps") is not None

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.freeze_time("2023-01-13 12:00:00+00:00")
async def test_identify_device(
    hass: HomeAssistant, mock_device: MockDevice, entity_registry: er.EntityRegistry
) -> None:
    """Test start PLC pairing button."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_identify_device_with_a_blinking_led"
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert (
        entity_registry.async_get(state_key).entity_category
        is EntityCategory.DIAGNOSTIC
    )

    # Emulate button press
    await hass.services.async_call(
        PLATFORM,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: state_key},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state.state == "2023-01-13T12:00:00+00:00"
    assert mock_device.plcnet.async_identify_device_start.call_count == 1

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.freeze_time("2023-01-13 12:00:00+00:00")
async def test_start_plc_pairing(hass: HomeAssistant, mock_device: MockDevice) -> None:
    """Test start PLC pairing button."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_start_plc_pairing"
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
    assert state.state == "2023-01-13T12:00:00+00:00"
    assert mock_device.plcnet.async_pair_device.call_count == 1

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.freeze_time("2023-01-13 12:00:00+00:00")
async def test_restart(
    hass: HomeAssistant, mock_device: MockDevice, entity_registry: er.EntityRegistry
) -> None:
    """Test restart button."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_restart_device"
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes["device_class"] == ButtonDeviceClass.RESTART
    assert entity_registry.async_get(state_key).entity_category is EntityCategory.CONFIG

    # Emulate button press
    await hass.services.async_call(
        PLATFORM,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: state_key},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state.state == "2023-01-13T12:00:00+00:00"
    assert mock_device.device.async_restart.call_count == 1

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.freeze_time("2023-01-13 12:00:00+00:00")
async def test_start_wps(hass: HomeAssistant, mock_device: MockDevice) -> None:
    """Test start WPS button."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_start_wps"

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
    assert state.state == "2023-01-13T12:00:00+00:00"
    assert mock_device.device.async_start_wps.call_count == 1

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    ("name", "trigger_method"),
    [
        ["identify_device_with_a_blinking_led", "async_identify_device_start"],
        ["start_plc_pairing", "async_pair_device"],
        ["restart_device", "async_restart"],
        ["start_wps", "async_start_wps"],
    ],
)
async def test_device_failure(
    hass: HomeAssistant,
    mock_device: MockDevice,
    name: str,
    trigger_method: str,
) -> None:
    """Test device failure."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_{name}"

    setattr(mock_device.device, trigger_method, AsyncMock())
    api = getattr(mock_device.device, trigger_method)
    api.side_effect = DeviceUnavailable
    setattr(mock_device.plcnet, trigger_method, AsyncMock())
    api = getattr(mock_device.plcnet, trigger_method)
    api.side_effect = DeviceUnavailable

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Emulate button press
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            PLATFORM,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: state_key},
            blocking=True,
        )
        await hass.async_block_till_done()

    await hass.config_entries.async_unload(entry.entry_id)


async def test_auth_failed(hass: HomeAssistant, mock_device: MockDevice) -> None:
    """Test setting unautherized triggers the reauth flow."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_start_wps"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_device.device.async_start_wps.side_effect = DevicePasswordProtected

    with pytest.raises(HomeAssistantError):
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
