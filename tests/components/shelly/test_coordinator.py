"""Tests for Shelly coordinator."""

from datetime import timedelta
from unittest.mock import AsyncMock, Mock, call, patch

from aioshelly.const import MODEL_BULB, MODEL_BUTTON1
from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.shelly import MacAddressMismatchError
from homeassistant.components.shelly.const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    ATTR_DEVICE,
    ATTR_GENERATION,
    CONF_BLE_SCANNER_MODE,
    CONF_SLEEP_PERIOD,
    DOMAIN,
    ENTRY_RELOAD_COOLDOWN,
    MAX_PUSH_UPDATE_FAILURES,
    RPC_RECONNECT_INTERVAL,
    UPDATE_PERIOD_MULTIPLIER,
    BLEScannerMode,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import Event, HomeAssistant, State
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from . import (
    MOCK_MAC,
    init_integration,
    inject_rpc_device_event,
    mock_polling_rpc_update,
    mock_rest_update,
    register_device,
    register_entity,
)

from tests.common import async_fire_time_changed, mock_restore_cache

RELAY_BLOCK_ID = 0
LIGHT_BLOCK_ID = 2
SENSOR_BLOCK_ID = 3
DEVICE_BLOCK_ID = 4


async def test_block_reload_on_cfg_change(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block reload on config change."""
    await init_integration(hass, 1)

    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "cfgChanged", 1)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    # Make sure cfgChanged with None is ignored
    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "cfgChanged", None)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    # Wait for debouncer
    freezer.tick(timedelta(seconds=ENTRY_RELOAD_COOLDOWN))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_name_channel_1")

    # Generate config change from switch to light
    monkeypatch.setitem(
        mock_block_device.settings["relays"][RELAY_BLOCK_ID], "appliance_type", "light"
    )
    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "cfgChanged", 2)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_name_channel_1")

    # Wait for debouncer
    freezer.tick(timedelta(seconds=ENTRY_RELOAD_COOLDOWN))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_name_channel_1") is None


async def test_block_no_reload_on_bulb_changes(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block no reload on bulb mode/effect change."""
    await init_integration(hass, 1, model=MODEL_BULB)

    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "cfgChanged", 1)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    # Test no reload  on mode change
    monkeypatch.setitem(
        mock_block_device.settings["relays"][RELAY_BLOCK_ID], "appliance_type", "light"
    )
    monkeypatch.setattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "mode", "white")
    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "cfgChanged", 2)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_name_channel_1")

    # Wait for debouncer
    freezer.tick(timedelta(seconds=ENTRY_RELOAD_COOLDOWN))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_name_channel_1")

    # Test no reload  on effect change
    monkeypatch.setattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "effect", 1)
    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "cfgChanged", 3)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_name_channel_1")

    # Wait for debouncer
    freezer.tick(timedelta(seconds=ENTRY_RELOAD_COOLDOWN))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_name_channel_1")


async def test_block_polling_auth_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block device polling authentication error."""
    monkeypatch.setattr(
        mock_block_device,
        "update",
        AsyncMock(side_effect=InvalidAuthError),
    )
    entry = await init_integration(hass, 1)

    assert entry.state is ConfigEntryState.LOADED

    # Move time to generate polling
    freezer.tick(timedelta(seconds=UPDATE_PERIOD_MULTIPLIER * 15))
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


async def test_block_rest_update_auth_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block REST update authentication error."""
    register_entity(hass, BINARY_SENSOR_DOMAIN, "test_name_cloud", "cloud")
    monkeypatch.setitem(mock_block_device.status, "cloud", {"connected": False})
    monkeypatch.setitem(mock_block_device.status, "uptime", 1)
    entry = await init_integration(hass, 1)

    monkeypatch.setattr(
        mock_block_device,
        "update_shelly",
        AsyncMock(side_effect=InvalidAuthError),
    )

    assert entry.state is ConfigEntryState.LOADED

    await mock_rest_update(hass, freezer)

    assert entry.state is ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_block_sleeping_device_firmware_unsupported(
    hass: HomeAssistant,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test block sleeping device firmware not supported."""
    monkeypatch.setattr(mock_block_device, "firmware_supported", False)
    entry = await init_integration(hass, 1, sleep_period=3600)

    # Make device online
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert (
        DOMAIN,
        "firmware_unsupported_123456789ABC",
    ) in issue_registry.issues


async def test_block_polling_connection_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block device polling connection error."""
    monkeypatch.setattr(
        mock_block_device,
        "update",
        AsyncMock(side_effect=DeviceConnectionError),
    )
    await init_integration(hass, 1)

    assert (state := hass.states.get("switch.test_name_channel_1"))
    assert state.state == STATE_ON

    # Move time to generate polling
    freezer.tick(timedelta(seconds=UPDATE_PERIOD_MULTIPLIER * 15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("switch.test_name_channel_1"))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("exc", [DeviceConnectionError, MacAddressMismatchError])
async def test_block_rest_update_connection_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    exc: Exception,
) -> None:
    """Test block REST update connection error."""
    entity_id = register_entity(hass, BINARY_SENSOR_DOMAIN, "test_name_cloud", "cloud")
    monkeypatch.setitem(mock_block_device.status, "cloud", {"connected": True})
    monkeypatch.setitem(mock_block_device.status, "uptime", 1)
    await init_integration(hass, 1)

    await mock_rest_update(hass, freezer)
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    monkeypatch.setattr(mock_block_device, "update_shelly", AsyncMock(side_effect=exc))
    await mock_rest_update(hass, freezer)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


async def test_block_sleeping_device_no_periodic_updates(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block sleeping device no periodic updates."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_temperature"
    monkeypatch.setitem(
        mock_block_device.settings,
        "sleep_mode",
        {"period": 60, "unit": "m"},
    )
    await init_integration(hass, 1, sleep_period=3600)

    # Make device online
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == "22.1"

    # Move time to generate polling
    freezer.tick(timedelta(seconds=UPDATE_PERIOD_MULTIPLIER * 3600))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


async def test_block_device_push_updates_failure(
    hass: HomeAssistant,
    mock_block_device: Mock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test block device with push updates failure."""
    await init_integration(hass, 1)

    # Updates with COAP_REPLAY type should create an issue
    for _ in range(MAX_PUSH_UPDATE_FAILURES):
        mock_block_device.mock_update_reply()
        await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        domain=DOMAIN, issue_id=f"push_update_{MOCK_MAC}"
    )

    # An update with COAP_PERIODIC type should clear the issue
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(
        domain=DOMAIN, issue_id=f"push_update_{MOCK_MAC}"
    )


async def test_block_button_click_event(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_block_device: Mock,
    events: list[Event],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test block click event for Shelly button."""
    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "sensor_ids", {})
    monkeypatch.setattr(
        mock_block_device.blocks[DEVICE_BLOCK_ID],
        "sensor_ids",
        {"inputEvent": "S", "inputEventCnt": 0},
    )
    entry = await init_integration(hass, 1, model=MODEL_BUTTON1, sleep_period=1000)

    # Make device online
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    # Generate button click event
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data == {
        ATTR_DEVICE_ID: device.id,
        ATTR_DEVICE: "test-host",
        ATTR_CHANNEL: 1,
        ATTR_CLICK_TYPE: "single",
        ATTR_GENERATION: 1,
    }

    # Test ignore empty event
    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "inputEvent", "")
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert len(events) == 1


async def test_rpc_reload_on_cfg_change(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC reload on config change."""
    monkeypatch.delitem(mock_rpc_device.status, "cover:0")
    monkeypatch.setitem(mock_rpc_device.status["sys"], "relay_in_thermostat", False)
    await init_integration(hass, 2)

    # Generate config change from switch to light
    monkeypatch.setitem(
        mock_rpc_device.config["sys"]["ui_data"], "consumption_types", ["lights"]
    )
    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "data": [],
                    "event": "config_changed",
                    "id": 1,
                    "ts": 1668522399.2,
                },
                {
                    "data": [],
                    "id": 2,
                    "ts": 1668522399.2,
                },
            ],
            "ts": 1668522399.2,
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_switch_0")

    # Wait for debouncer
    freezer.tick(timedelta(seconds=ENTRY_RELOAD_COOLDOWN))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_switch_0") is None


async def test_rpc_reload_with_invalid_auth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC when InvalidAuthError is raising during config entry reload."""
    with patch(
        "homeassistant.components.shelly.coordinator.async_stop_scanner",
        side_effect=[None, InvalidAuthError, None],
    ):
        entry = await init_integration(hass, 2)

        inject_rpc_device_event(
            monkeypatch,
            mock_rpc_device,
            {
                "events": [
                    {
                        "data": [],
                        "event": "config_changed",
                        "id": 1,
                        "ts": 1668522399.2,
                    },
                    {
                        "data": [],
                        "id": 2,
                        "ts": 1668522399.2,
                    },
                ],
                "ts": 1668522399.2,
            },
        )

        await hass.async_block_till_done()

        # Move time to generate reconnect
        freezer.tick(timedelta(seconds=RPC_RECONNECT_INTERVAL))
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


async def test_rpc_connection_error_during_unload(
    hass: HomeAssistant, mock_rpc_device: Mock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test RPC DeviceConnectionError suppressed during config entry unload."""
    entry = await init_integration(hass, 2)

    assert entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.components.shelly.coordinator.async_stop_scanner",
        side_effect=DeviceConnectionError,
    ):
        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

    assert "Error during shutdown for device" in caplog.text
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_rpc_click_event(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_rpc_device: Mock,
    events: list[Event],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC click event."""
    entry = await init_integration(hass, 2)

    device = dr.async_entries_for_config_entry(device_registry, entry.entry_id)[0]

    # Generate config change from switch to light
    inject_rpc_device_event(
        monkeypatch,
        mock_rpc_device,
        {
            "events": [
                {
                    "data": [],
                    "event": "single_push",
                    "id": 0,
                    "ts": 1668522399.2,
                }
            ],
            "ts": 1668522399.2,
        },
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data == {
        ATTR_DEVICE_ID: device.id,
        ATTR_DEVICE: "test-host",
        ATTR_CHANNEL: 1,
        ATTR_CLICK_TYPE: "single_push",
        ATTR_GENERATION: 2,
    }


async def test_rpc_update_entry_sleep_period(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC update entry sleep period."""
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 600)
    entry = await init_integration(hass, 2, sleep_period=600)
    register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_temperature",
        "temperature:0-temperature_0",
        entry,
    )

    # Make device online
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.data[CONF_SLEEP_PERIOD] == 600

    # Move time to generate sleep period update
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 3600)
    freezer.tick(timedelta(seconds=600 * UPDATE_PERIOD_MULTIPLIER))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.data[CONF_SLEEP_PERIOD] == 3600


async def test_rpc_sleeping_device_no_periodic_updates(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC sleeping device no periodic updates."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_temperature"
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
    entry = await init_integration(hass, 2, sleep_period=1000)
    register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_temperature",
        "temperature:0-temperature_0",
        entry,
    )

    # Make device online
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == "22.9"

    # Move time to generate polling
    freezer.tick(timedelta(seconds=UPDATE_PERIOD_MULTIPLIER * 1000))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


async def test_rpc_sleeping_device_firmware_unsupported(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test RPC sleeping device firmware not supported."""
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setattr(mock_rpc_device, "firmware_supported", False)
    entry = await init_integration(hass, 2, sleep_period=3600)

    # Make device online
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert (
        DOMAIN,
        "firmware_unsupported_123456789ABC",
    ) in issue_registry.issues


async def test_rpc_reconnect_auth_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC reconnect authentication error."""
    entry = await init_integration(hass, 2)

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
    freezer.tick(timedelta(seconds=RPC_RECONNECT_INTERVAL))
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
    entry = await init_integration(hass, 2)

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
    monkeypatch.delitem(mock_rpc_device.status, "cover:0")
    monkeypatch.setitem(mock_rpc_device.status["sys"], "relay_in_thermostat", False)
    await init_integration(hass, 2)

    assert (state := hass.states.get("switch.test_switch_0"))
    assert state.state == STATE_ON

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setattr(mock_rpc_device, "initialize", AsyncMock(side_effect=exc))

    # Move time to generate reconnect
    freezer.tick(timedelta(seconds=RPC_RECONNECT_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("switch.test_switch_0"))
    assert state.state == STATE_UNAVAILABLE


async def test_rpc_error_running_connected_events(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test RPC error while running connected events."""
    monkeypatch.delitem(mock_rpc_device.status, "cover:0")
    monkeypatch.setitem(mock_rpc_device.status["sys"], "relay_in_thermostat", False)
    with patch(
        "homeassistant.components.shelly.coordinator.async_ensure_ble_enabled",
        side_effect=DeviceConnectionError,
    ):
        await init_integration(
            hass, 2, options={CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE}
        )

    assert "Error running connected events for device" in caplog.text

    assert (state := hass.states.get("switch.test_switch_0"))
    assert state.state == STATE_UNAVAILABLE

    # Move time to generate reconnect without error
    freezer.tick(timedelta(seconds=RPC_RECONNECT_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get("switch.test_switch_0"))
    assert state.state == STATE_ON


async def test_rpc_polling_connection_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC polling connection error."""
    entity_id = register_entity(hass, SENSOR_DOMAIN, "test_name_rssi", "wifi-rssi")
    await init_integration(hass, 2)

    monkeypatch.setattr(
        mock_rpc_device,
        "poll",
        AsyncMock(
            side_effect=DeviceConnectionError,
        ),
    )

    assert (state := hass.states.get(entity_id))
    assert state.state == "-63"

    await mock_polling_rpc_update(hass, freezer)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


async def test_rpc_polling_disconnected(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC polling device disconnected."""
    entity_id = register_entity(hass, SENSOR_DOMAIN, "test_name_rssi", "wifi-rssi")
    await init_integration(hass, 2)

    monkeypatch.setattr(mock_rpc_device, "connected", False)

    assert (state := hass.states.get(entity_id))
    assert state.state == "-63"

    await mock_polling_rpc_update(hass, freezer)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


async def test_rpc_update_entry_fw_ver(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC update entry firmware version."""
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 600)
    entry = await init_integration(hass, 2, sleep_period=600)

    # Make device online
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.unique_id
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.entry_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(entry.unique_id))},
    )
    assert device
    assert device.sw_version == "some fw string"

    monkeypatch.setattr(mock_rpc_device, "firmware_version", "99.0.0")

    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.entry_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(entry.unique_id))},
    )
    assert device
    assert device.sw_version == "99.0.0"


@pytest.mark.parametrize(("supports_scripts"), [True, False])
async def test_rpc_runs_connected_events_when_initialized(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    supports_scripts: bool,
) -> None:
    """Test RPC runs connected events when initialized."""
    monkeypatch.setattr(
        mock_rpc_device, "supports_scripts", AsyncMock(return_value=supports_scripts)
    )
    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    await init_integration(hass, 2)

    assert call.script_list() not in mock_rpc_device.mock_calls

    # Mock initialized event
    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_initialized()
    await hass.async_block_till_done()

    assert call.supports_scripts() in mock_rpc_device.mock_calls
    # BLE script list is called during connected events if device supports scripts
    assert bool(call.script_list() in mock_rpc_device.mock_calls) == supports_scripts


async def test_rpc_sleeping_device_unload_ignore_ble_scanner(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC sleeping device does not stop ble scanner on unload."""
    monkeypatch.setattr(mock_rpc_device, "connected", True)
    entry = await init_integration(hass, 2, sleep_period=1000)

    # Make device online
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    # Unload
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    # BLE script list is called during stop ble scanner
    assert call.script_list() not in mock_rpc_device.mock_calls


async def test_block_sleeping_device_connection_error(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_block_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test block sleeping device connection error during initialize."""
    sleep_period = 1000
    entry = await init_integration(hass, 1, sleep_period=sleep_period, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        BINARY_SENSOR_DOMAIN,
        "test_name_motion",
        "sensor_0-motion",
        entry,
        device_id=device.id,
    )
    mock_restore_cache(hass, [State(entity_id, STATE_ON)])
    monkeypatch.setattr(mock_block_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    # Make device online event with connection error
    monkeypatch.setattr(
        mock_block_device,
        "initialize",
        AsyncMock(
            side_effect=DeviceConnectionError,
        ),
    )
    mock_block_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Error connecting to Shelly device" in caplog.text
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    # Move time to generate sleep period update
    freezer.tick(timedelta(seconds=sleep_period * UPDATE_PERIOD_MULTIPLIER))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Sleeping device did not update" in caplog.text
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


async def test_rpc_sleeping_device_connection_error(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test RPC sleeping device connection error during initialize."""
    sleep_period = 1000
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    device = register_device(device_registry, entry)
    entity_id = register_entity(
        hass,
        BINARY_SENSOR_DOMAIN,
        "test_name_cloud",
        "cloud-cloud",
        entry,
        device_id=device.id,
    )
    mock_restore_cache(hass, [State(entity_id, STATE_ON)])
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    # Make device online event with connection error
    monkeypatch.setattr(
        mock_rpc_device,
        "initialize",
        AsyncMock(
            side_effect=DeviceConnectionError,
        ),
    )
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Error connecting to Shelly device" in caplog.text
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_ON

    # Move time to generate sleep period update
    freezer.tick(timedelta(seconds=sleep_period * UPDATE_PERIOD_MULTIPLIER))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "Sleeping device did not update" in caplog.text
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


async def test_rpc_sleeping_device_late_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test RPC sleeping device creates entities if they do not exist yet."""
    entry = await init_integration(hass, 2, sleep_period=1000, skip_setup=True)
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 1000)
    assert entry.data[CONF_SLEEP_PERIOD] == 1000
    register_device(device_registry, entry)
    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setattr(mock_rpc_device, "initialized", False)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    monkeypatch.setattr(mock_rpc_device, "initialized", True)
    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)
    monkeypatch.setattr(mock_rpc_device, "connected", True)
    mock_rpc_device.mock_initialized()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get("sensor.test_name_temperature")


async def test_rpc_already_connected(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_rpc_device: Mock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test RPC ignore connect event if already connected."""
    await init_integration(hass, 2)

    mock_rpc_device.mock_online()
    await hass.async_block_till_done(wait_background_tasks=True)

    assert "already connected" in caplog.text
    mock_rpc_device.initialize.assert_called_once()


async def test_xmod_model_lookup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test XMOD model look-up."""
    xmod_model = "Test XMOD model name"
    monkeypatch.setattr(mock_rpc_device, "xmod_info", {"n": xmod_model})
    entry = await init_integration(hass, 2)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.entry_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, dr.format_mac(entry.unique_id))},
    )
    assert device
    assert device.model == xmod_model
