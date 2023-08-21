"""Tests for Shelly coordinator."""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aioshelly.exceptions import DeviceConnectionError, InvalidAuthError

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.shelly.const import (
    ATTR_CHANNEL,
    ATTR_CLICK_TYPE,
    ATTR_DEVICE,
    ATTR_GENERATION,
    DOMAIN,
    ENTRY_RELOAD_COOLDOWN,
    MAX_PUSH_UPDATE_FAILURES,
    RPC_RECONNECT_INTERVAL,
    SLEEP_PERIOD_MULTIPLIER,
    UPDATE_PERIOD_MULTIPLIER,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    async_entries_for_config_entry,
    async_get as async_get_dev_reg,
)
import homeassistant.helpers.issue_registry as ir
from homeassistant.util import dt as dt_util

from . import (
    MOCK_MAC,
    init_integration,
    inject_rpc_device_event,
    mock_polling_rpc_update,
    mock_rest_update,
    register_entity,
)

from tests.common import async_fire_time_changed

RELAY_BLOCK_ID = 0
LIGHT_BLOCK_ID = 2
SENSOR_BLOCK_ID = 3
DEVICE_BLOCK_ID = 4


async def test_block_reload_on_cfg_change(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block reload on config change."""
    await init_integration(hass, 1)

    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "cfgChanged", 1)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    # Generate config change from switch to light
    monkeypatch.setitem(
        mock_block_device.settings["relays"][RELAY_BLOCK_ID], "appliance_type", "light"
    )
    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "cfgChanged", 2)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_name_channel_1") is not None

    # Wait for debouncer
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_name_channel_1") is None


async def test_block_no_reload_on_bulb_changes(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block no reload on bulb mode/effect change."""
    await init_integration(hass, 1, model="SHBLB-1")

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

    assert hass.states.get("switch.test_name_channel_1") is not None

    # Wait for debouncer
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_name_channel_1") is not None

    # Test no reload  on effect change
    monkeypatch.setattr(mock_block_device.blocks[LIGHT_BLOCK_ID], "effect", 1)
    monkeypatch.setattr(mock_block_device.blocks[DEVICE_BLOCK_ID], "cfgChanged", 3)
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_name_channel_1") is not None

    # Wait for debouncer
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_name_channel_1") is not None


async def test_block_polling_auth_error(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device polling authentication error."""
    monkeypatch.setattr(
        mock_block_device,
        "update",
        AsyncMock(side_effect=InvalidAuthError),
    )
    entry = await init_integration(hass, 1)

    assert entry.state == ConfigEntryState.LOADED

    # Move time to generate polling
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=UPDATE_PERIOD_MULTIPLIER * 15)
    )
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_block_rest_update_auth_error(
    hass: HomeAssistant, mock_block_device, monkeypatch
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

    assert entry.state == ConfigEntryState.LOADED

    await mock_rest_update(hass)

    assert entry.state == ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_block_polling_connection_error(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device polling connection error."""
    monkeypatch.setattr(
        mock_block_device,
        "update",
        AsyncMock(side_effect=DeviceConnectionError),
    )
    await init_integration(hass, 1)

    assert hass.states.get("switch.test_name_channel_1").state == STATE_ON

    # Move time to generate polling
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=UPDATE_PERIOD_MULTIPLIER * 15)
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_name_channel_1").state == STATE_UNAVAILABLE


async def test_block_rest_update_connection_error(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block REST update connection error."""
    entity_id = register_entity(hass, BINARY_SENSOR_DOMAIN, "test_name_cloud", "cloud")
    monkeypatch.setitem(mock_block_device.status, "cloud", {"connected": True})
    monkeypatch.setitem(mock_block_device.status, "uptime", 1)
    await init_integration(hass, 1)

    await mock_rest_update(hass)
    assert hass.states.get(entity_id).state == STATE_ON

    monkeypatch.setattr(
        mock_block_device,
        "update_shelly",
        AsyncMock(side_effect=DeviceConnectionError),
    )
    await mock_rest_update(hass)

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_block_sleeping_device_no_periodic_updates(
    hass: HomeAssistant, mock_block_device
) -> None:
    """Test block sleeping device no periodic updates."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_temperature"
    await init_integration(hass, 1, sleep_period=1000)

    # Make device online
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "22.1"

    # Move time to generate polling
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=SLEEP_PERIOD_MULTIPLIER * 1000)
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_block_device_push_updates_failure(
    hass: HomeAssistant, mock_block_device, monkeypatch
) -> None:
    """Test block device with push updates failure."""
    issue_registry: ir.IssueRegistry = ir.async_get(hass)

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
    hass: HomeAssistant, mock_block_device, events, monkeypatch
) -> None:
    """Test block click event for Shelly button."""
    monkeypatch.setattr(mock_block_device.blocks[RELAY_BLOCK_ID], "sensor_ids", {})
    monkeypatch.setattr(
        mock_block_device.blocks[DEVICE_BLOCK_ID],
        "sensor_ids",
        {"inputEvent": "S", "inputEventCnt": 0},
    )
    entry = await init_integration(hass, 1, model="SHBTN-1", sleep_period=1000)

    # Make device online
    mock_block_device.mock_update()
    await hass.async_block_till_done()

    dev_reg = async_get_dev_reg(hass)
    device = async_entries_for_config_entry(dev_reg, entry.entry_id)[0]

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
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC reload on config change."""
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

    assert hass.states.get("switch.test_name_test_switch_0") is not None

    # Wait for debouncer
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=ENTRY_RELOAD_COOLDOWN)
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_name_test_switch_0") is None


async def test_rpc_reload_with_invalid_auth(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
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
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=RPC_RECONNECT_INTERVAL)
        )
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_rpc_click_event(
    hass: HomeAssistant, mock_rpc_device, events, monkeypatch
) -> None:
    """Test RPC click event."""
    entry = await init_integration(hass, 2)

    dev_reg = async_get_dev_reg(hass)
    device = async_entries_for_config_entry(dev_reg, entry.entry_id)[0]

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
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC update entry sleep period."""
    entry = await init_integration(hass, 2, sleep_period=600)
    register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_temperature",
        "temperature:0-temperature_0",
        entry,
    )

    # Make device online
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert entry.data["sleep_period"] == 600

    # Move time to generate sleep period update
    monkeypatch.setitem(mock_rpc_device.status["sys"], "wakeup_period", 3600)
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=600 * SLEEP_PERIOD_MULTIPLIER)
    )
    await hass.async_block_till_done()

    assert entry.data["sleep_period"] == 3600


async def test_rpc_sleeping_device_no_periodic_updates(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC sleeping device no periodic updates."""
    entity_id = f"{SENSOR_DOMAIN}.test_name_temperature"
    entry = await init_integration(hass, 2, sleep_period=1000)
    register_entity(
        hass,
        SENSOR_DOMAIN,
        "test_name_temperature",
        "temperature:0-temperature_0",
        entry,
    )

    # Make device online
    mock_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "22.9"

    # Move time to generate polling
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=SLEEP_PERIOD_MULTIPLIER * 1000)
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_rpc_reconnect_auth_error(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
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

    assert entry.state == ConfigEntryState.LOADED

    # Move time to generate reconnect
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RPC_RECONNECT_INTERVAL)
    )
    await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_rpc_polling_auth_error(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC polling authentication error."""
    register_entity(hass, SENSOR_DOMAIN, "test_name_rssi", "wifi-rssi")
    entry = await init_integration(hass, 2)

    monkeypatch.setattr(
        mock_rpc_device,
        "update_status",
        AsyncMock(
            side_effect=InvalidAuthError,
        ),
    )

    assert entry.state == ConfigEntryState.LOADED

    await mock_polling_rpc_update(hass)

    assert entry.state == ConfigEntryState.LOADED

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == entry.entry_id


async def test_rpc_reconnect_error(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC reconnect error."""
    await init_integration(hass, 2)

    assert hass.states.get("switch.test_name_test_switch_0").state == STATE_ON

    monkeypatch.setattr(mock_rpc_device, "connected", False)
    monkeypatch.setattr(
        mock_rpc_device,
        "initialize",
        AsyncMock(
            side_effect=DeviceConnectionError,
        ),
    )

    # Move time to generate reconnect
    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=RPC_RECONNECT_INTERVAL)
    )
    await hass.async_block_till_done()

    assert hass.states.get("switch.test_name_test_switch_0").state == STATE_UNAVAILABLE


async def test_rpc_polling_connection_error(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC polling connection error."""
    entity_id = register_entity(hass, SENSOR_DOMAIN, "test_name_rssi", "wifi-rssi")
    await init_integration(hass, 2)

    monkeypatch.setattr(
        mock_rpc_device,
        "update_status",
        AsyncMock(
            side_effect=DeviceConnectionError,
        ),
    )

    assert hass.states.get(entity_id).state == "-63"

    await mock_polling_rpc_update(hass)

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


async def test_rpc_polling_disconnected(
    hass: HomeAssistant, mock_rpc_device, monkeypatch
) -> None:
    """Test RPC polling device disconnected."""
    entity_id = register_entity(hass, SENSOR_DOMAIN, "test_name_rssi", "wifi-rssi")
    await init_integration(hass, 2)

    monkeypatch.setattr(mock_rpc_device, "connected", False)

    assert hass.states.get(entity_id).state == "-63"

    await mock_polling_rpc_update(hass)

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
