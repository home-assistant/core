"""Tests for the devolo Home Network update."""

from devolo_plc_api.device_api import UPDATE_NOT_AVAILABLE, UpdateFirmwareCheck
from devolo_plc_api.exceptions.device import DevicePasswordProtected, DeviceUnavailable
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.devolo_home_network.const import (
    DOMAIN,
    FIRMWARE_UPDATE_INTERVAL,
)
from homeassistant.components.update import DOMAIN as PLATFORM, SERVICE_INSTALL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import configure_integration
from .const import FIRMWARE_UPDATE_AVAILABLE
from .mock import MockDevice

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("mock_device")
async def test_update_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test default setup of the update component."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert not entity_registry.async_get(f"{PLATFORM}.{device_name}_firmware").disabled


async def test_update_firmware(
    hass: HomeAssistant,
    mock_device: MockDevice,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test updating a device."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_firmware"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(state_key) == snapshot
    assert entity_registry.async_get(state_key) == snapshot

    await hass.services.async_call(
        PLATFORM,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: state_key},
        blocking=True,
    )
    assert mock_device.device.async_start_firmware_update.call_count == 1

    # Emulate state change
    mock_device.firmware_version = FIRMWARE_UPDATE_AVAILABLE.new_firmware_version.split(
        "_"
    )[0]
    mock_device.device.async_check_firmware_available.return_value = (
        UpdateFirmwareCheck(result=UPDATE_NOT_AVAILABLE)
    )
    freezer.tick(FIRMWARE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_OFF

    device_info = device_registry.async_get_device(
        {(DOMAIN, mock_device.serial_number)}
    )
    assert device_info is not None
    assert device_info.sw_version == mock_device.firmware_version


async def test_device_failure_check(
    hass: HomeAssistant,
    mock_device: MockDevice,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test device failure during check."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_firmware"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None

    mock_device.device.async_check_firmware_available.side_effect = DeviceUnavailable
    freezer.tick(FIRMWARE_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_device_failure_update(
    hass: HomeAssistant,
    mock_device: MockDevice,
) -> None:
    """Test device failure when starting update."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_firmware"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_device.device.async_start_firmware_update.side_effect = DeviceUnavailable

    # Emulate update start
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            PLATFORM,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: state_key},
            blocking=True,
        )


async def test_auth_failed(hass: HomeAssistant, mock_device: MockDevice) -> None:
    """Test updating unauthorized triggers the reauth flow."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_firmware"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    mock_device.device.async_start_firmware_update.side_effect = DevicePasswordProtected

    with pytest.raises(HomeAssistantError):
        assert await hass.services.async_call(
            PLATFORM,
            SERVICE_INSTALL,
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
