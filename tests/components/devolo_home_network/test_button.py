"""Tests for the devolo Home Network buttons."""

from unittest.mock import AsyncMock

from devolo_plc_api.exceptions.device import DevicePasswordProtected, DeviceUnavailable
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as PLATFORM, SERVICE_PRESS
from homeassistant.components.devolo_home_network.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import configure_integration
from .mock import MockDevice


@pytest.mark.usefixtures("mock_device")
async def test_button_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test default setup of the button component."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert not entity_registry.async_get(
        f"{PLATFORM}.{device_name}_identify_device_with_a_blinking_led"
    ).disabled
    assert not entity_registry.async_get(
        f"{PLATFORM}.{device_name}_start_plc_pairing"
    ).disabled
    assert not entity_registry.async_get(
        f"{PLATFORM}.{device_name}_restart_device"
    ).disabled
    assert not entity_registry.async_get(f"{PLATFORM}.{device_name}_start_wps").disabled


@pytest.mark.parametrize(
    ("name", "api_name", "trigger_method"),
    [
        (
            "identify_device_with_a_blinking_led",
            "plcnet",
            "async_identify_device_start",
        ),
        (
            "start_plc_pairing",
            "plcnet",
            "async_pair_device",
        ),
        (
            "restart_device",
            "device",
            "async_restart",
        ),
        (
            "start_wps",
            "device",
            "async_start_wps",
        ),
    ],
)
@pytest.mark.freeze_time("2023-01-13 12:00:00+00:00")
async def test_button(
    hass: HomeAssistant,
    mock_device: MockDevice,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    name: str,
    api_name: str,
    trigger_method: str,
) -> None:
    """Test a button."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_{name}"
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(state_key) == snapshot
    assert entity_registry.async_get(state_key) == snapshot

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
    api = getattr(mock_device, api_name)
    assert getattr(api, trigger_method).call_count == 1

    # Emulate device failure
    setattr(api, trigger_method, AsyncMock())
    getattr(api, trigger_method).side_effect = DeviceUnavailable
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            PLATFORM,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: state_key},
            blocking=True,
        )


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
