"""Tests for refoss_rpc coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock, call

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.refoss_rpc import (
    DeviceConnectionError,
    InvalidAuthError,
    MacAddressMismatchError,
)
from homeassistant.components.refoss_rpc.const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    ATTR_DEVICE,
    DOMAIN,
    ENTRY_RELOAD_COOLDOWN,
    REFOSS_CHECK_INTERVAL,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import (
    get_entity_state,
    inject_rpc_device_event,
    mock_polling_rpc_update,
    register_entity,
    set_integration,
)

from tests.common import async_fire_time_changed


async def test_rpc_reload_on_cfg_change(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test  reload on config change."""
    await set_integration(hass)

    monkeypatch.setitem(mock_rpc_device.config["input:1"], "type", "switch")
    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "event": "config_changed",
                    "ts": 1736925488,
                }
            ],
            "ts": 1736925488,
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get("event.test_input") is not None

    # Wait for debouncer
    freezer.tick(timedelta(seconds=ENTRY_RELOAD_COOLDOWN))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("event.test_input") is None


async def test_rpc_click_event(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_rpc_device: Mock,
    events: list[Event],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC click event."""
    entry = await set_integration(hass)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "event": "button_single_push",
                    "id": 1,
                    "ts": 1736925488,
                }
            ],
            "ts": 1736925488,
        },
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data == {
        ATTR_DEVICE_ID: device.id,
        ATTR_DEVICE: "Test name",
        ATTR_CHANNEL: 1,
        ATTR_CLICK_TYPE: "button_single_push",
    }


async def test_rpc_reconnect_auth_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC reconnect authentication error."""
    entry = await set_integration(hass)

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setattr(
        mock_rpc_device,
        "initialize",
        AsyncMock(
            side_effect=InvalidAuthError,
        ),
    )

    assert entry.state is ConfigEntryState.LOADED

    # Move time to generate reconnect
    freezer.tick(timedelta(seconds=REFOSS_CHECK_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_rpc_polling_auth_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC polling authentication error."""
    register_entity(hass, SENSOR_DOMAIN, "test_name_rssi", "wifi-rssi")
    entry = await set_integration(hass)

    monkeypatch.setattr(
        mock_rpc_device,
        "poll",
        AsyncMock(
            side_effect=InvalidAuthError,
        ),
    )

    assert entry.state is ConfigEntryState.LOADED

    await mock_polling_rpc_update(hass, freezer)

    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


@pytest.mark.parametrize("exc", [DeviceConnectionError, MacAddressMismatchError])
async def test_rpc_reconnect_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    exc: Exception,
) -> None:
    """Test RPC reconnect error."""
    await set_integration(hass)

    assert get_entity_state(hass, "switch.test_switch") == STATE_ON

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setattr(mock_rpc_device, "initialize", AsyncMock(side_effect=exc))

    # Move time to generate reconnect
    freezer.tick(timedelta(seconds=REFOSS_CHECK_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert get_entity_state(hass, "switch.test_switch") == STATE_UNAVAILABLE


async def test_rpc_polling_connection_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC polling connection error."""
    entity_id = register_entity(hass, SENSOR_DOMAIN, "test_name_rssi", "wifi-rssi")
    await set_integration(hass)

    monkeypatch.setattr(
        mock_rpc_device,
        "poll",
        AsyncMock(
            side_effect=DeviceConnectionError,
        ),
    )

    assert get_entity_state(hass, entity_id) == "-30"

    await mock_polling_rpc_update(hass, freezer)

    assert get_entity_state(hass, entity_id) == STATE_UNAVAILABLE


async def test_rpc_polling_disconnected(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC polling device disconnected."""
    entity_id = register_entity(hass, SENSOR_DOMAIN, "test_name_rssi", "wifi-rssi")
    await set_integration(hass)

    monkeypatch.setattr(
        mock_rpc_device,
        "poll",
        AsyncMock(
            side_effect=DeviceConnectionError,
        ),
    )

    assert get_entity_state(hass, entity_id) == "-30"

    await mock_polling_rpc_update(hass, freezer)

    assert get_entity_state(hass, entity_id) == STATE_UNAVAILABLE


async def test_rpc_update_entry_fw_ver(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC update entry firmware version."""
    entry = await set_integration(hass)

    assert entry.unique_id
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.entry_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(entry.unique_id))},
    )
    assert device
    assert device.sw_version == "1"

    # Make device online
    monkeypatch.setattr(mock_rpc_device, "firmware_version", "2")
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.entry_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(entry.unique_id))},
    )
    assert device
    assert device.sw_version == "2"


async def test_rpc_runs_connected_events_when_initialized(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC runs connected events when initialized."""
    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    await set_integration(hass)

    assert call.script_list() not in mock_rpc_device.mock_calls

    # Mock initialized event
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_initialized()
    await hass.async_block_till_done()


async def test_rpc_runs_connected_events_when_initialized_false(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC runs connected events when initialized."""
    await set_integration(hass)
    assert call.script_list() not in mock_rpc_device.mock_calls

    # Mock initialized event
    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    mock_rpc_device.mock_initialized()
    await hass.async_block_till_done()


async def test_rpc_already_connected(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test RPC ignore connect event if already connected."""
    await set_integration(hass)

    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "already connected" in caplog.text
    mock_rpc_device.initialize.assert_called_once()
