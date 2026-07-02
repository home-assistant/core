"""Test repairs handling for Shelly."""

from typing import Any
from unittest.mock import Mock, patch

from aioshelly.const import MODEL_PLUG, MODEL_WALL_DISPLAY
from aioshelly.exceptions import DeviceConnectionError, NotInitialized, RpcCallError
import pytest

from homeassistant.components.shelly import (
    async_replace_device,
    repairs as shelly_repairs,
)
from homeassistant.components.shelly.const import (
    BLE_SCANNER_FIRMWARE_UNSUPPORTED_ISSUE_ID,
    COIOT_UNCONFIGURED_ISSUE_ID,
    CONF_BLE_SCANNER_MODE,
    DEPRECATED_FIRMWARE_ISSUE_ID,
    DEVICE_CONFLICT_ISSUE_ID,
    DOMAIN,
    OPEN_WIFI_AP_ISSUE_ID,
    OUTBOUND_WEBSOCKET_INCORRECTLY_ENABLED_ISSUE_ID,
    PUSH_UPDATE_ISSUE_ID,
    BLEScannerMode,
    DeprecatedFirmwareInfo,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.device_registry import (
    CONNECTION_BLUETOOTH,
    CONNECTION_NETWORK_MAC,
)
from homeassistant.helpers.network import NoURLAvailableError
from homeassistant.setup import async_setup_component

from . import MOCK_MAC, init_integration, mock_block_device_push_update_failure

from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator

# The replacement device's MAC address (distinct from MOCK_MAC). Upper-case bare
# form mirrors how zeroconf discovery hands the new MAC to the repair flow.
NEW_MAC = "AABBCCDDEEFF"
# A BLU/bthome sub-device is keyed by its own BLE address, independent of the
# gateway Wi-Fi MAC, and must be left untouched by the transplant.
BLU_ADDR = "11:22:33:44:55:66"


async def test_ble_scanner_unsupported_firmware_issue(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_rpc_device: Mock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair issues handling for BLE scanner with unsupported firmware."""
    issue_id = BLE_SCANNER_FIRMWARE_UNSUPPORTED_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await init_integration(
        hass, 2, options={CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE}
    )

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, flow_id)
    assert result["type"] == "create_entry"
    assert mock_rpc_device.trigger_ota_update.call_count == 1

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0


async def test_unsupported_firmware_issue_update_not_available(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair issues handling when firmware update is not available."""
    issue_id = BLE_SCANNER_FIRMWARE_UNSUPPORTED_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await init_integration(
        hass, 2, options={CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE}
    )

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "confirm"

    monkeypatch.setitem(mock_rpc_device.status, "sys", {"available_updates": {}})
    result = await process_repair_fix_flow(client, flow_id)
    assert result["type"] == "abort"
    assert result["reason"] == "update_not_available"
    assert mock_rpc_device.trigger_ota_update.call_count == 0

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1


@pytest.mark.parametrize(
    "exception", [DeviceConnectionError, RpcCallError(999, "Unknown error")]
)
async def test_unsupported_firmware_issue_exc(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_rpc_device: Mock,
    issue_registry: ir.IssueRegistry,
    exception: Exception,
) -> None:
    """Test repair issues handling when OTA update ends with an exception."""
    issue_id = BLE_SCANNER_FIRMWARE_UNSUPPORTED_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await init_integration(
        hass, 2, options={CONF_BLE_SCANNER_MODE: BLEScannerMode.ACTIVE}
    )

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "confirm"

    mock_rpc_device.trigger_ota_update.side_effect = exception
    result = await process_repair_fix_flow(client, flow_id)
    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"
    assert mock_rpc_device.trigger_ota_update.call_count == 1

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1


async def test_outbound_websocket_incorrectly_enabled_issue(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_rpc_device: Mock,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test repair issues handling for the outbound WebSocket incorrectly enabled."""
    ws_url = "ws://10.10.10.10:8123/api/shelly/ws"
    monkeypatch.setitem(
        mock_rpc_device.config, "ws", {"enable": True, "server": ws_url}
    )

    issue_id = OUTBOUND_WEBSOCKET_INCORRECTLY_ENABLED_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await init_integration(hass, 2)

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, flow_id)
    assert result["type"] == "create_entry"
    assert mock_rpc_device.ws_setconfig.call_count == 1
    assert mock_rpc_device.ws_setconfig.call_args[0] == (False, ws_url)
    assert mock_rpc_device.trigger_reboot.call_count == 1

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0


async def test_repairs_skipped_when_device_not_initialized(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair checks are skipped when the RPC device is not initialized."""
    mock_rpc_device.initialized = False
    type(mock_rpc_device).config = property(
        lambda self: (_ for _ in ()).throw(NotInitialized)
    )

    await init_integration(hass, 2)

    assert len(issue_registry.issues) == 0


@pytest.mark.parametrize(
    "exception", [DeviceConnectionError, RpcCallError(999, "Unknown error")]
)
async def test_outbound_websocket_incorrectly_enabled_issue_exc(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_rpc_device: Mock,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
) -> None:
    """Test repair issues handling when ws_setconfig ends with an exception."""
    ws_url = "ws://10.10.10.10:8123/api/shelly/ws"
    monkeypatch.setitem(
        mock_rpc_device.config, "ws", {"enable": True, "server": ws_url}
    )

    issue_id = OUTBOUND_WEBSOCKET_INCORRECTLY_ENABLED_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await init_integration(hass, 2)

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "confirm"

    mock_rpc_device.ws_setconfig.side_effect = exception
    result = await process_repair_fix_flow(client, flow_id)
    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"
    assert mock_rpc_device.ws_setconfig.call_count == 1

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1


async def test_deprecated_firmware_issue(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_rpc_device: Mock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair issues handling deprecated firmware."""
    issue_id = DEPRECATED_FIRMWARE_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.shelly.repairs.DEPRECATED_FIRMWARES",
        {
            MODEL_WALL_DISPLAY: DeprecatedFirmwareInfo(
                {"min_firmware": "2.3.0", "ha_version": "2025.10.0"}
            )
        },
    ):
        await init_integration(hass, 2, model=MODEL_WALL_DISPLAY)

    # The default fw version in tests is 1.0.0, the repair issue should be created.
    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, flow_id)
    assert result["type"] == "create_entry"
    assert mock_rpc_device.trigger_ota_update.call_count == 1

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0


async def test_open_wifi_ap_issue(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_rpc_device: Mock,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test repair issues handling for open WiFi AP."""
    monkeypatch.setitem(
        mock_rpc_device.config,
        "wifi",
        {"ap": {"enable": True, "is_open": True}},
    )

    issue_id = OPEN_WIFI_AP_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await init_integration(hass, 2)

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "init"
    assert result["type"] == "menu"

    result = await process_repair_fix_flow(client, flow_id, {"next_step_id": "confirm"})
    assert result["type"] == "create_entry"
    assert mock_rpc_device.wifi_setconfig.call_count == 1
    assert mock_rpc_device.wifi_setconfig.call_args[1] == {"ap_enable": False}
    assert mock_rpc_device.trigger_reboot.call_count == 1

    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0


async def test_open_wifi_ap_issue_no_restart(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_rpc_device: Mock,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test repair issues handling for open WiFi AP when restart not required."""
    monkeypatch.setitem(
        mock_rpc_device.config,
        "wifi",
        {"ap": {"enable": True, "is_open": True}},
    )

    issue_id = OPEN_WIFI_AP_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await init_integration(hass, 2)

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "init"
    assert result["type"] == "menu"

    mock_rpc_device.wifi_setconfig.return_value = {"restart_required": False}

    result = await process_repair_fix_flow(client, flow_id, {"next_step_id": "confirm"})
    assert result["type"] == "create_entry"
    assert mock_rpc_device.wifi_setconfig.call_count == 1
    assert mock_rpc_device.wifi_setconfig.call_args[1] == {"ap_enable": False}
    assert mock_rpc_device.trigger_reboot.call_count == 0

    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0


@pytest.mark.parametrize(
    "exception", [DeviceConnectionError, RpcCallError(999, "Unknown error")]
)
async def test_open_wifi_ap_issue_exc(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_rpc_device: Mock,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    exception: Exception,
) -> None:
    """Test repair issues handling when wifi_setconfig ends with an exception."""
    monkeypatch.setitem(
        mock_rpc_device.config,
        "wifi",
        {"ap": {"enable": True, "is_open": True}},
    )

    issue_id = OPEN_WIFI_AP_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await init_integration(hass, 2)

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "init"
    assert result["type"] == "menu"

    mock_rpc_device.wifi_setconfig.side_effect = exception
    result = await process_repair_fix_flow(client, flow_id, {"next_step_id": "confirm"})
    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"
    assert mock_rpc_device.wifi_setconfig.call_count == 1

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1


async def test_no_open_wifi_ap_issue_with_password(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test no repair issue is created when WiFi AP has a password."""
    monkeypatch.setitem(
        mock_rpc_device.config,
        "wifi",
        {"ap": {"enable": True, "is_open": False}},
    )

    issue_id = OPEN_WIFI_AP_ISSUE_ID.format(unique=MOCK_MAC)
    await init_integration(hass, 2)

    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0


async def test_no_open_wifi_ap_issue_when_disabled(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test no repair issue is created when WiFi AP is disabled."""
    monkeypatch.setitem(
        mock_rpc_device.config,
        "wifi",
        {"ap": {"enable": False, "is_open": True}},
    )

    issue_id = OPEN_WIFI_AP_ISSUE_ID.format(unique=MOCK_MAC)
    await init_integration(hass, 2)

    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0


async def test_open_wifi_ap_issue_ignore(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_rpc_device: Mock,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test ignoring the open WiFi AP issue."""
    monkeypatch.setitem(
        mock_rpc_device.config,
        "wifi",
        {"ap": {"enable": True, "is_open": True}},
    )

    issue_id = OPEN_WIFI_AP_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await init_integration(hass, 2)

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "init"
    assert result["type"] == "menu"

    result = await process_repair_fix_flow(client, flow_id, {"next_step_id": "ignore"})
    assert result["type"] == "abort"
    assert result["reason"] == "issue_ignored"
    assert mock_rpc_device.wifi_setconfig.call_count == 0

    assert (issue := issue_registry.async_get_issue(DOMAIN, issue_id))
    assert issue.dismissed_version


@pytest.mark.parametrize(
    "ignore_missing_translations", ["component.shelly.issues.other_issue.title"]
)
async def test_other_fixable_issues(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_rpc_device: Mock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test fixing another issue."""
    issue_id = "other_issue"
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    entry = await init_integration(hass, 2)
    assert mock_rpc_device.initialized is True

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        data={"entry_id": entry.entry_id},
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="other_issue",
    )

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "confirm"
    assert result["type"] == "form"

    result = await process_repair_fix_flow(client, flow_id)
    assert result["type"] == "create_entry"


@pytest.mark.parametrize(
    "coiot",
    [
        {"enabled": False, "update_period": 15, "peer": "10.10.10.10:5683"},
        {"enabled": True, "update_period": 15, "peer": "7.7.7.7:5683"},
    ],
)
async def test_coiot_disabled_or_wrong_peer_issue(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_block_device: Mock,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    coiot: dict[str, Any],
) -> None:
    """Test repair issues handling wrong or disabled CoIoT configuration."""
    monkeypatch.setitem(mock_block_device.settings, "coiot", coiot)
    issue_id = COIOT_UNCONFIGURED_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await init_integration(hass, 1)
    await mock_block_device_push_update_failure(hass, mock_block_device)

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "init"
    assert result["type"] == "menu"

    result = await process_repair_fix_flow(client, flow_id, {"next_step_id": "confirm"})

    assert result["type"] == "create_entry"
    assert mock_block_device.configure_coiot_protocol.call_count == 1

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 0


async def test_coiot_exception(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_block_device: Mock,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test CoIoT exception handling in fix flow."""
    monkeypatch.setitem(
        mock_block_device.settings,
        "coiot",
        {"enabled": False, "update_period": 15, "peer": "7.7.7.7:5683"},
    )
    issue_id = COIOT_UNCONFIGURED_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await init_integration(hass, 1)
    await mock_block_device_push_update_failure(hass, mock_block_device)

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "init"
    assert result["type"] == "menu"

    mock_block_device.configure_coiot_protocol.side_effect = DeviceConnectionError
    result = await process_repair_fix_flow(client, flow_id, {"next_step_id": "confirm"})

    assert result["type"] == "abort"
    assert result["reason"] == "cannot_connect"
    assert mock_block_device.configure_coiot_protocol.call_count == 1

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1


@pytest.mark.parametrize(
    "raw_url",
    [
        "http://10.10.10.10:8123",
        "https://homeassistant.local:443",
    ],
)
async def test_coiot_configured_no_issue_created(
    hass: HomeAssistant,
    mock_block_device: Mock,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
    raw_url: str,
) -> None:
    """Test no repair issues when CoIoT configuration is valid."""
    issue_id = COIOT_UNCONFIGURED_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    with patch(
        "homeassistant.components.shelly.utils.get_url",
        return_value=raw_url,
    ):
        await hass.async_block_till_done()
        await init_integration(hass, 1)
        await mock_block_device_push_update_failure(hass, mock_block_device)

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_coiot_key_missing_no_issue_created(
    hass: HomeAssistant,
    mock_block_device: Mock,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test no repair issues when CoIoT configuration is missing."""
    monkeypatch.delitem(
        mock_block_device.settings,
        "coiot",
    )
    issue_id = COIOT_UNCONFIGURED_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await init_integration(hass, 1)

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_coiot_push_issue_when_missing_hass_url(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_block_device: Mock,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test CoIoT push update issue created when HA URL is not available."""
    issue_id = PUSH_UPDATE_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await init_integration(hass, 1)

    with patch(
        "homeassistant.components.shelly.utils.get_url",
        side_effect=NoURLAvailableError(),
    ):
        await mock_block_device_push_update_failure(hass, mock_block_device)

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1


async def test_coiot_fix_flow_no_hass_url(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_block_device: Mock,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test CoIoT repair issue when HA URL is not available."""
    monkeypatch.setitem(
        mock_block_device.settings,
        "coiot",
        {"enabled": False, "update_period": 15, "peer": "7.7.7.7:5683"},
    )
    issue_id = COIOT_UNCONFIGURED_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await init_integration(hass, 1)
    await mock_block_device_push_update_failure(hass, mock_block_device)

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "init"
    assert result["type"] == "menu"

    with patch(
        "homeassistant.components.shelly.utils.get_url",
        side_effect=NoURLAvailableError(),
    ):
        result = await process_repair_fix_flow(
            client, flow_id, {"next_step_id": "confirm"}
        )

        assert result["type"] == "abort"
        assert result["reason"] == "cannot_configure"
        assert mock_block_device.configure_coiot_protocol.call_count == 0

        assert issue_registry.async_get_issue(DOMAIN, issue_id)
        assert len(issue_registry.issues) == 1


async def test_coiot_issue_ignore(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_block_device: Mock,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test ignoring the CoIoT unconfigured issue."""
    monkeypatch.setitem(
        mock_block_device.settings,
        "coiot",
        {"enabled": False, "update_period": 15, "peer": "7.7.7.7:5683"},
    )
    issue_id = COIOT_UNCONFIGURED_ISSUE_ID.format(unique=MOCK_MAC)

    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await init_integration(hass, 1)
    await mock_block_device_push_update_failure(hass, mock_block_device)

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "init"
    assert result["type"] == "menu"

    result = await process_repair_fix_flow(client, flow_id, {"next_step_id": "ignore"})
    assert result["type"] == "abort"
    assert result["reason"] == "issue_ignored"
    assert mock_block_device.configure_coiot_protocol.call_count == 0

    assert (issue := issue_registry.async_get_issue(DOMAIN, issue_id))
    assert issue.dismissed_version


async def test_plug_1_push_update_issue_created(
    hass: HomeAssistant,
    mock_block_device: Mock,
    issue_registry: ir.IssueRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test push update repair issue when device is Shelly Plug 1."""
    monkeypatch.setattr(mock_block_device, "model", MODEL_PLUG)
    issue_id = PUSH_UPDATE_ISSUE_ID.format(unique=MOCK_MAC)
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await init_integration(hass, 1, model=MODEL_PLUG)
    await mock_block_device_push_update_failure(hass, mock_block_device)

    assert issue_registry.async_get_issue(DOMAIN, issue_id)
    assert len(issue_registry.issues) == 1


def _seed_device_conflict_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entry: ConfigEntry,
) -> tuple[str, str, str]:
    """Seed a sub-device, an entity and an untouched BLU sub-device.

    The main device (identifier ``(DOMAIN, MOCK_MAC)`` + the MAC connection) is
    already created by ``init_integration``. Returns the entity_id of the
    seeded entity plus the ids of the seeded sub- and BLU devices.
    """
    # A regular, MAC-prefixed sub-device (e.g. switch:0) whose identifier the
    # transplant must rewrite.
    sub_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{MOCK_MAC}-switch_0")},
        via_device=(DOMAIN, MOCK_MAC),
    )
    # An entity whose unique_id carries the old MAC prefix.
    entity_entry = entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{MOCK_MAC}-switch:0",
        suggested_object_id="test_switch_0",
        config_entry=entry,
        device_id=sub_device.id,
    )
    # A BLU/bthome sub-device keyed by its own BLE address (not the Wi-Fi MAC).
    # The transplant must NOT touch it.
    blu_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, BLU_ADDR)},
        connections={(CONNECTION_BLUETOOTH, BLU_ADDR)},
        via_device=(DOMAIN, MOCK_MAC),
    )
    # A BLU entity, prefixed by the BLE address, that must also stay untouched.
    entity_registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{BLU_ADDR}-temperature",
        suggested_object_id="blu_temperature",
        config_entry=entry,
        device_id=blu_device.id,
    )
    return entity_entry.entity_id, sub_device.id, blu_device.id


def _create_device_conflict_issue(hass: HomeAssistant, entry: ConfigEntry) -> str:
    """Create the device_conflict repair issue for an entry, return its id."""
    issue_id = DEVICE_CONFLICT_ISSUE_ID.format(unique=entry.entry_id)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="device_conflict",
        translation_placeholders={
            "device_name": "Test name",
            "host": "192.168.1.37",
            "old_mac": dr.format_mac(MOCK_MAC).upper(),
            "new_mac": dr.format_mac(NEW_MAC).upper(),
        },
        data={
            "entry_id": entry.entry_id,
            "device_name": "Test name",
            "host": "192.168.1.37",
            "old_mac": MOCK_MAC,
            "new_mac": NEW_MAC,
        },
    )
    return issue_id


async def _run_device_conflict_migrate(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    gen: int,
) -> None:
    """Drive the device_conflict migrate path and assert the full transplant.

    The config entry unique_id, the main device connections/identifiers, a
    sub-device identifier prefix and the entity unique_ids are rewritten from
    the old MAC to the new MAC, while entity_ids are preserved and
    BLU/bluetooth sub-devices stay untouched.
    """
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    entry = await init_integration(hass, gen)

    entity_id, _sub_id, blu_id = _seed_device_conflict_registry(
        hass, device_registry, entity_registry, entry
    )

    # Capture pre-migration state. init_integration stores the unique_id as the
    # upper-case bare MAC; HA does not normalise it (it is not colon-separated).
    assert entry.unique_id == MOCK_MAC
    assert (entity_entry := entity_registry.async_get(entity_id))
    assert entity_entry.unique_id == f"{MOCK_MAC}-switch:0"
    blu_before = device_registry.async_get(blu_id)
    assert blu_before is not None
    assert (DOMAIN, BLU_ADDR) in blu_before.identifiers
    assert (CONNECTION_BLUETOOTH, BLU_ADDR) in blu_before.connections

    issue_id = _create_device_conflict_issue(hass, entry)
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["type"] == "menu"
    assert result["step_id"] == "init"
    assert result["description_placeholders"]["new_mac"] == "AA:BB:CC:DD:EE:FF"

    result = await process_repair_fix_flow(client, flow_id, {"next_step_id": "migrate"})
    assert result["type"] == "form"
    assert result["step_id"] == "migrate"

    with patch.object(hass.config_entries, "async_schedule_reload"):
        result = await process_repair_fix_flow(client, flow_id)
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()

    new_upper = NEW_MAC

    # Config entry unique_id swapped to the new MAC, kept UPPER-case bare to
    # match Shelly's identity convention (coordinator.mac == entry.unique_id
    # feeds the device identifier and entity unique_ids). A lower-case flip
    # here would make a reload re-derive a MAC that no longer matches the
    # registry, creating a duplicate main device.
    assert entry.unique_id == new_upper

    # Main device: new connection present, old gone; identifier rewritten.
    main_device = device_registry.async_get_device(identifiers={(DOMAIN, new_upper)})
    assert main_device is not None
    # The entry unique_id must equal the main device's DOMAIN identifier MAC,
    # so the post-reload coordinator re-matches the same device.
    assert (DOMAIN, entry.unique_id) in main_device.identifiers
    assert (CONNECTION_NETWORK_MAC, dr.format_mac(NEW_MAC)) in main_device.connections
    assert (
        CONNECTION_NETWORK_MAC,
        dr.format_mac(MOCK_MAC),
    ) not in main_device.connections
    assert (DOMAIN, MOCK_MAC) not in main_device.identifiers
    assert device_registry.async_get_device(identifiers={(DOMAIN, MOCK_MAC)}) is None

    # Sub-device identifier prefix rewritten old -> new.
    sub_device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{new_upper}-switch_0")}
    )
    assert sub_device is not None
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, f"{MOCK_MAC}-switch_0")})
        is None
    )

    # Entity unique_id rewritten, entity_id preserved.
    migrated_entity = entity_registry.async_get(entity_id)
    assert migrated_entity is not None
    assert migrated_entity.entity_id == entity_id
    assert migrated_entity.unique_id == f"{new_upper}-switch:0"
    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        if entity.unique_id.startswith(BLU_ADDR):
            continue
        assert not entity.unique_id.startswith(MOCK_MAC)

    # BLU sub-device and its entity untouched.
    blu_after = device_registry.async_get(blu_id)
    assert blu_after is not None
    assert (DOMAIN, BLU_ADDR) in blu_after.identifiers
    assert (CONNECTION_BLUETOOTH, BLU_ADDR) in blu_after.connections
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BLU_ADDR}-temperature"
    )

    # The issue is resolved by the framework on create_entry.
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_device_conflict_migrate_block(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_block_device: Mock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the migrate path transplant for a Gen1 Block device."""
    await _run_device_conflict_migrate(
        hass, hass_client, device_registry, entity_registry, issue_registry, 1
    )


async def test_device_conflict_migrate_rpc(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the migrate path transplant for a Gen2 RPC device."""
    await _run_device_conflict_migrate(
        hass, hass_client, device_registry, entity_registry, issue_registry, 2
    )


async def _run_device_conflict_manual(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    gen: int,
) -> None:
    """Drive the device_conflict manual path; it clears the issue, no transplant."""
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    entry = await init_integration(hass, gen)

    entity_id, _sub_id, _blu_id = _seed_device_conflict_registry(
        hass, device_registry, entity_registry, entry
    )

    issue_id = _create_device_conflict_issue(hass, entry)
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["type"] == "menu"
    assert result["step_id"] == "init"

    result = await process_repair_fix_flow(client, flow_id, {"next_step_id": "manual"})
    assert result["type"] == "form"
    assert result["step_id"] == "manual"

    with patch.object(hass.config_entries, "async_schedule_reload") as mock_reload:
        result = await process_repair_fix_flow(client, flow_id)
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()

    # Manual path only reloads, it must not transplant anything.
    mock_reload.assert_called_once_with(entry.entry_id)
    assert entry.unique_id == MOCK_MAC
    assert device_registry.async_get_device(identifiers={(DOMAIN, MOCK_MAC)})
    assert device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_MAC}-switch_0")}
    )
    migrated_entity = entity_registry.async_get(entity_id)
    assert migrated_entity is not None
    assert migrated_entity.unique_id == f"{MOCK_MAC}-switch:0"

    # The issue is resolved by the framework on create_entry.
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_device_conflict_manual_block(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_block_device: Mock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the manual path for a Gen1 Block device."""
    await _run_device_conflict_manual(
        hass, hass_client, device_registry, entity_registry, issue_registry, 1
    )


async def test_device_conflict_manual_rpc(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the manual path for a Gen2 RPC device."""
    await _run_device_conflict_manual(
        hass, hass_client, device_registry, entity_registry, issue_registry, 2
    )


async def test_device_conflict_fix_flow_routing(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
) -> None:
    """Test async_create_fix_flow routes a device_conflict issue id correctly.

    Unlike ESPHome (which raises ValueError on an unknown issue id), the Shelly
    router falls back to a ConfirmRepairFlow, so the assertion here is that the
    ``device_conflict`` prefix routes to the dedicated flow and carries the
    issue data through to the flow properties.
    """
    entry = await init_integration(hass, 2)

    data = {
        "entry_id": entry.entry_id,
        "device_name": "Test name",
        "host": "192.168.1.37",
        "old_mac": MOCK_MAC,
        "new_mac": NEW_MAC,
    }
    flow = await shelly_repairs.async_create_fix_flow(
        hass, DEVICE_CONFLICT_ISSUE_ID.format(unique=entry.entry_id), data
    )
    assert isinstance(flow, shelly_repairs.DeviceConflictRepairFlow)
    assert flow.entry_id == entry.entry_id
    assert flow.old_mac == MOCK_MAC
    assert flow.new_mac == NEW_MAC


async def test_device_conflict_placeholders_missing_issue(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the placeholder lookup returns None when the issue is gone.

    If the repair issue is resolved or removed mid-flow, the issue registry no
    longer holds its translation placeholders. ``_description_placeholders``
    must then fall back to ``None`` instead of raising.
    """
    entry = await init_integration(hass, 2)

    data = {
        "entry_id": entry.entry_id,
        "device_name": "Test name",
        "host": "192.168.1.37",
        "old_mac": MOCK_MAC,
        "new_mac": NEW_MAC,
    }
    issue_id = DEVICE_CONFLICT_ISSUE_ID.format(unique=entry.entry_id)
    flow = await shelly_repairs.async_create_fix_flow(hass, issue_id, data)
    assert isinstance(flow, shelly_repairs.DeviceConflictRepairFlow)

    # Drive the flow's placeholder lookup directly. No issue was created in the
    # registry for this id, so the lookup must hit the None fallback.
    flow.hass = hass
    flow.issue_id = issue_id
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
    assert flow._description_placeholders() is None


async def test_async_replace_device_skips_bluetooth(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test async_replace_device leaves BLU/bluetooth sub-devices untouched.

    Exercises the module-level transplant directly (no flow) to assert the
    bluetooth guard in isolation for the RPC generation.
    """
    entry = await init_integration(hass, 2)
    _entity_id, _sub_id, blu_id = _seed_device_conflict_registry(
        hass, device_registry, entity_registry, entry
    )

    await async_replace_device(hass, entry.entry_id, MOCK_MAC, NEW_MAC)
    await hass.async_block_till_done()

    blu_after = device_registry.async_get(blu_id)
    assert blu_after is not None
    assert (DOMAIN, BLU_ADDR) in blu_after.identifiers
    assert (CONNECTION_BLUETOOTH, BLU_ADDR) in blu_after.connections
    assert entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{BLU_ADDR}-temperature"
    )
    # And the main + sub-device WERE migrated.
    assert device_registry.async_get_device(identifiers={(DOMAIN, NEW_MAC)})
    assert device_registry.async_get_device(
        identifiers={(DOMAIN, f"{NEW_MAC}-switch_0")}
    )


async def test_async_replace_device_normalizes_mac_input(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test async_replace_device normalizes colon/lower-case MAC inputs.

    The real producer (zeroconf detection) may hand the transplant a
    colon-separated or lower-case MAC, so the function must normalise both the
    old and the new MAC to the upper-case bare form before substituting.
    """
    entry = await init_integration(hass, 2)
    entity_id, _sub_id, _blu_id = _seed_device_conflict_registry(
        hass, device_registry, entity_registry, entry
    )

    # Feed the old MAC colon-separated/lower-case and the new MAC lower-case
    # bare; the end state must be identical to the upper-case path.
    old_mac_coloned = "12:34:56:78:9a:bc"
    new_mac_lower = NEW_MAC.lower()
    await async_replace_device(hass, entry.entry_id, old_mac_coloned, new_mac_lower)
    await hass.async_block_till_done()

    # Entry unique_id is the upper-case bare new MAC.
    assert entry.unique_id == NEW_MAC

    # Main + sub-device identifiers rewritten to the upper-case new MAC.
    assert device_registry.async_get_device(identifiers={(DOMAIN, NEW_MAC)})
    assert device_registry.async_get_device(identifiers={(DOMAIN, MOCK_MAC)}) is None
    assert device_registry.async_get_device(
        identifiers={(DOMAIN, f"{NEW_MAC}-switch_0")}
    )
    # Connection rewritten to the lower-case colon form.
    main_device = device_registry.async_get_device(identifiers={(DOMAIN, NEW_MAC)})
    assert main_device is not None
    assert (CONNECTION_NETWORK_MAC, dr.format_mac(NEW_MAC)) in main_device.connections

    # Entity unique_id prefix rewritten to the upper-case new MAC.
    migrated_entity = entity_registry.async_get(entity_id)
    assert migrated_entity is not None
    assert migrated_entity.unique_id == f"{NEW_MAC}-switch:0"


async def test_async_replace_device_does_not_over_match_prefix(
    hass: HomeAssistant,
    mock_rpc_device: Mock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the transplant does not rewrite identifiers that only share a prefix.

    Pins the trailing-``-`` boundary of the guard: a sub-device whose
    identifier starts with the old MAC but is NOT followed by ``-`` (e.g. a
    longer MAC that has the old MAC as a substring prefix), and an entity that
    shares the same loose prefix, must be left untouched.
    """
    entry = await init_integration(hass, 2)

    # A device whose identifier shares the MOCK_MAC string as a prefix but is a
    # different (longer) MAC, so it must NOT be rewritten. The trailing "-"
    # guard is what protects it.
    prefixy_mac = f"{MOCK_MAC}00"
    prefixy_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, f"{prefixy_mac}-switch_0")},
        via_device=(DOMAIN, MOCK_MAC),
    )
    # An entity that also shares the loose prefix but not the "-" boundary.
    prefixy_entity = entity_registry.async_get_or_create(
        "switch",
        DOMAIN,
        f"{prefixy_mac}-switch:0",
        suggested_object_id="prefixy_switch_0",
        config_entry=entry,
        device_id=prefixy_device.id,
    )

    await async_replace_device(hass, entry.entry_id, MOCK_MAC, NEW_MAC)
    await hass.async_block_till_done()

    # The prefix-sharing device and entity are untouched.
    assert device_registry.async_get_device(
        identifiers={(DOMAIN, f"{prefixy_mac}-switch_0")}
    )
    assert (
        device_registry.async_get_device(
            identifiers={(DOMAIN, f"{NEW_MAC}00-switch_0")}
        )
        is None
    )
    untouched_entity = entity_registry.async_get(prefixy_entity.entity_id)
    assert untouched_entity is not None
    assert untouched_entity.unique_id == f"{prefixy_mac}-switch:0"
