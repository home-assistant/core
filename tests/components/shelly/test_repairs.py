"""Test repairs handling for Shelly."""

from unittest.mock import Mock, patch

from aioshelly.const import MODEL_WALL_DISPLAY
from aioshelly.exceptions import DeviceConnectionError, RpcCallError
import pytest

from homeassistant.components.shelly.const import (
    BLE_SCANNER_FIRMWARE_UNSUPPORTED_ISSUE_ID,
    CONF_BLE_SCANNER_MODE,
    DEPRECATED_FIRMWARE_ISSUE_ID,
    DOMAIN,
    OPEN_WIFI_AP_ISSUE_ID,
    OUTBOUND_WEBSOCKET_INCORRECTLY_ENABLED_ISSUE_ID,
    BLEScannerMode,
    DeprecatedFirmwareInfo,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import MOCK_MAC, init_integration

from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator


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

    await async_process_repairs_platforms(hass)
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

    await async_process_repairs_platforms(hass)
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

    await async_process_repairs_platforms(hass)
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

    await async_process_repairs_platforms(hass)
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

    await async_process_repairs_platforms(hass)
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

    await async_process_repairs_platforms(hass)
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

    await async_process_repairs_platforms(hass)
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

    await async_process_repairs_platforms(hass)
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

    await async_process_repairs_platforms(hass)
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

    await async_process_repairs_platforms(hass)
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "init"
    assert result["type"] == "menu"

    result = await process_repair_fix_flow(client, flow_id, {"next_step_id": "ignore"})
    assert result["type"] == "abort"
    assert result["reason"] == "issue_ignored"
    assert mock_rpc_device.wifi_setconfig.call_count == 0

    assert issue_registry.async_get_issue(DOMAIN, issue_id).dismissed_version


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

    await async_process_repairs_platforms(hass)
    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["step_id"] == "confirm"
    assert result["type"] == "form"

    result = await process_repair_fix_flow(client, flow_id)
    assert result["type"] == "create_entry"
