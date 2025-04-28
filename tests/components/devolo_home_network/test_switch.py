"""Tests for the devolo Home Network switch."""

from datetime import timedelta
from unittest.mock import AsyncMock

from devolo_plc_api.device_api import WifiGuestAccessGet
from devolo_plc_api.exceptions.device import DevicePasswordProtected, DeviceUnavailable
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.devolo_home_network.const import (
    DOMAIN,
    SHORT_UPDATE_INTERVAL,
)
from homeassistant.components.switch import DOMAIN as PLATFORM
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
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
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import REQUEST_REFRESH_DEFAULT_COOLDOWN

from . import configure_integration
from .mock import MockDevice

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("mock_device")
async def test_switch_setup(hass: HomeAssistant) -> None:
    """Test default setup of the switch component."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(f"{PLATFORM}.{device_name}_enable_guest_wi_fi") is not None
    assert hass.states.get(f"{PLATFORM}.{device_name}_enable_leds") is not None

    await hass.config_entries.async_unload(entry.entry_id)


async def test_update_guest_wifi_status_auth_failed(
    hass: HomeAssistant, mock_device: MockDevice
) -> None:
    """Test getting the wifi_status with wrong password triggers the reauth flow."""
    entry = configure_integration(hass)
    mock_device.device.async_get_wifi_guest_access.side_effect = DevicePasswordProtected

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN

    assert "context" in flow
    assert flow["context"]["source"] == SOURCE_REAUTH
    assert flow["context"]["entry_id"] == entry.entry_id

    await hass.config_entries.async_unload(entry.entry_id)


async def test_update_enable_guest_wifi(
    hass: HomeAssistant,
    mock_device: MockDevice,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test state change of a enable_guest_wifi switch device."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_enable_guest_wi_fi"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(state_key) == snapshot
    assert entity_registry.async_get(state_key) == snapshot

    # Emulate state change
    mock_device.device.async_get_wifi_guest_access.return_value = WifiGuestAccessGet(
        enabled=True
    )
    freezer.tick(SHORT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_ON

    # Switch off
    mock_device.device.async_get_wifi_guest_access.return_value = WifiGuestAccessGet(
        enabled=False
    )
    await hass.services.async_call(
        PLATFORM, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: state_key}, blocking=True
    )

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_OFF
    mock_device.device.async_set_wifi_guest_access.assert_called_once_with(False)
    mock_device.device.async_set_wifi_guest_access.reset_mock()

    freezer.tick(REQUEST_REFRESH_DEFAULT_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Switch on
    mock_device.device.async_get_wifi_guest_access.return_value = WifiGuestAccessGet(
        enabled=True
    )
    await hass.services.async_call(
        PLATFORM, SERVICE_TURN_ON, {ATTR_ENTITY_ID: state_key}, blocking=True
    )

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_ON
    mock_device.device.async_set_wifi_guest_access.assert_called_once_with(True)
    mock_device.device.async_set_wifi_guest_access.reset_mock()

    freezer.tick(REQUEST_REFRESH_DEFAULT_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Device unavailable
    mock_device.device.async_get_wifi_guest_access.side_effect = DeviceUnavailable()
    mock_device.device.async_set_wifi_guest_access.side_effect = DeviceUnavailable()

    with pytest.raises(
        HomeAssistantError, match=f"Device {entry.title} did not respond"
    ):
        await hass.services.async_call(
            PLATFORM, SERVICE_TURN_ON, {ATTR_ENTITY_ID: state_key}, blocking=True
        )
    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_unload(entry.entry_id)


async def test_update_enable_leds(
    hass: HomeAssistant,
    mock_device: MockDevice,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test state change of a enable_leds switch device."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_enable_leds"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(state_key) == snapshot
    assert entity_registry.async_get(state_key) == snapshot

    # Emulate state change
    mock_device.device.async_get_led_setting.return_value = True
    freezer.tick(SHORT_UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_ON

    # Switch off
    mock_device.device.async_get_led_setting.return_value = False
    await hass.services.async_call(
        PLATFORM, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: state_key}, blocking=True
    )

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_OFF
    mock_device.device.async_set_led_setting.assert_called_once_with(False)
    mock_device.device.async_set_led_setting.reset_mock()

    freezer.tick(REQUEST_REFRESH_DEFAULT_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Switch on
    mock_device.device.async_get_led_setting.return_value = True
    await hass.services.async_call(
        PLATFORM, SERVICE_TURN_ON, {ATTR_ENTITY_ID: state_key}, blocking=True
    )

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_ON
    mock_device.device.async_set_led_setting.assert_called_once_with(True)
    mock_device.device.async_set_led_setting.reset_mock()

    freezer.tick(REQUEST_REFRESH_DEFAULT_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Device unavailable
    mock_device.device.async_get_led_setting.side_effect = DeviceUnavailable()
    mock_device.device.async_set_led_setting.side_effect = DeviceUnavailable()

    with pytest.raises(
        HomeAssistantError, match=f"Device {entry.title} did not respond"
    ):
        await hass.services.async_call(
            PLATFORM, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: state_key}, blocking=True
        )
    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    ("name", "get_method", "update_interval"),
    [
        ("enable_guest_wi_fi", "async_get_wifi_guest_access", SHORT_UPDATE_INTERVAL),
        ("enable_leds", "async_get_led_setting", SHORT_UPDATE_INTERVAL),
    ],
)
async def test_device_failure(
    hass: HomeAssistant,
    mock_device: MockDevice,
    freezer: FrozenDateTimeFactory,
    name: str,
    get_method: str,
    update_interval: timedelta,
) -> None:
    """Test device failure."""
    entry = configure_integration(hass)
    device_name = entry.title.replace(" ", "_").lower()
    state_key = f"{PLATFORM}.{device_name}_{name}"

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None

    api = getattr(mock_device.device, get_method)
    api.side_effect = DeviceUnavailable
    freezer.tick(update_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(state_key)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("name", "set_method"),
    [
        ("enable_guest_wi_fi", "async_set_wifi_guest_access"),
        ("enable_leds", "async_set_led_setting"),
    ],
)
async def test_auth_failed(
    hass: HomeAssistant, mock_device: MockDevice, name: str, set_method: str
) -> None:
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

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            PLATFORM, SERVICE_TURN_ON, {ATTR_ENTITY_ID: state_key}, blocking=True
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

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            PLATFORM, SERVICE_TURN_OFF, {"entity_id": state_key}, blocking=True
        )
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert "context" in flow
    assert flow["context"]["source"] == SOURCE_REAUTH
    assert flow["context"]["entry_id"] == entry.entry_id

    await hass.config_entries.async_unload(entry.entry_id)
