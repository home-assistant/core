"""Repairs flow for Shelly."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aioshelly.const import MODEL_OUT_PLUG_S_G3, MODEL_PLUG_S_G3
from aioshelly.exceptions import DeviceConnectionError, RpcCallError
from aioshelly.rpc_device import RpcDevice
from awesomeversion import AwesomeVersion
import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import (
    BLE_SCANNER_FIRMWARE_UNSUPPORTED_ISSUE_ID,
    BLE_SCANNER_MIN_FIRMWARE,
    CONF_BLE_SCANNER_MODE,
    DEPRECATED_FIRMWARE_ISSUE_ID,
    DOMAIN,
    OUTBOUND_WEBSOCKET_INCORRECTLY_ENABLED_ISSUE_ID,
    BLEScannerMode,
)
from .coordinator import ShellyConfigEntry
from .utils import get_rpc_ws_url


@callback
def async_manage_ble_scanner_firmware_unsupported_issue(
    hass: HomeAssistant,
    entry: ShellyConfigEntry,
) -> None:
    """Manage the BLE scanner firmware unsupported issue."""
    issue_id = BLE_SCANNER_FIRMWARE_UNSUPPORTED_ISSUE_ID.format(unique=entry.unique_id)

    if TYPE_CHECKING:
        assert entry.runtime_data.rpc is not None

    device = entry.runtime_data.rpc.device
    supports_scripts = entry.runtime_data.rpc_supports_scripts

    if supports_scripts and device.model not in (MODEL_PLUG_S_G3, MODEL_OUT_PLUG_S_G3):
        firmware = AwesomeVersion(device.shelly["ver"])
        if (
            firmware < BLE_SCANNER_MIN_FIRMWARE
            and entry.options.get(CONF_BLE_SCANNER_MODE) == BLEScannerMode.ACTIVE
        ):
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=True,
                is_persistent=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key="ble_scanner_firmware_unsupported",
                translation_placeholders={
                    "device_name": device.name,
                    "ip_address": device.ip_address,
                    "firmware": firmware,
                },
                data={"entry_id": entry.entry_id},
            )
            return

    ir.async_delete_issue(hass, DOMAIN, issue_id)


@callback
def async_manage_deprecated_firmware_issue(
    hass: HomeAssistant,
    entry: ShellyConfigEntry,
    model: str,
    min_firmware: str,
    ha_version: str,
) -> None:
    """Manage deprecated firmware issue."""
    issue_id = DEPRECATED_FIRMWARE_ISSUE_ID.format(unique=entry.unique_id)

    if TYPE_CHECKING:
        assert entry.runtime_data.rpc is not None

    device = entry.runtime_data.rpc.device

    if entry.data["model"] == model:
        firmware = AwesomeVersion(device.shelly["ver"])
        if firmware < min_firmware:
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=True,
                is_persistent=True,
                severity=ir.IssueSeverity.WARNING,
                translation_key="deprecated_firmware",
                translation_placeholders={
                    "device_name": device.name,
                    "ip_address": device.ip_address,
                    "firmware": firmware,
                    "ha_version": ha_version,
                },
                data={"entry_id": entry.entry_id},
            )
            return

    ir.async_delete_issue(hass, DOMAIN, issue_id)


@callback
def async_manage_outbound_websocket_incorrectly_enabled_issue(
    hass: HomeAssistant,
    entry: ShellyConfigEntry,
) -> None:
    """Manage the Outbound WebSocket incorrectly enabled issue."""
    issue_id = OUTBOUND_WEBSOCKET_INCORRECTLY_ENABLED_ISSUE_ID.format(
        unique=entry.unique_id
    )

    if TYPE_CHECKING:
        assert entry.runtime_data.rpc is not None

    device = entry.runtime_data.rpc.device

    if (
        (ws_config := device.config.get("ws"))
        and ws_config["enable"]
        and ws_config["server"] == get_rpc_ws_url(hass)
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=True,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="outbound_websocket_incorrectly_enabled",
            translation_placeholders={
                "device_name": device.name,
                "ip_address": device.ip_address,
            },
            data={"entry_id": entry.entry_id},
        )
        return

    ir.async_delete_issue(hass, DOMAIN, issue_id)


class ShellyRpcRepairsFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, device: RpcDevice) -> None:
        """Initialize."""
        self._device = device

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            return await self._async_step_confirm()

        issue_registry = ir.async_get(self.hass)
        description_placeholders = None
        if issue := issue_registry.async_get_issue(self.handler, self.issue_id):
            description_placeholders = issue.translation_placeholders

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=description_placeholders,
        )

    async def _async_step_confirm(self) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        raise NotImplementedError


class FirmwareUpdateFlow(ShellyRpcRepairsFlow):
    """Handler for Firmware Update flow."""

    async def _async_step_confirm(self) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        return await self.async_step_update_firmware()

    async def async_step_update_firmware(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if not self._device.status["sys"]["available_updates"]:
            return self.async_abort(reason="update_not_available")
        try:
            await self._device.trigger_ota_update()
        except (DeviceConnectionError, RpcCallError):
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title="", data={})


class DisableOutboundWebSocketFlow(ShellyRpcRepairsFlow):
    """Handler for Disable Outbound WebSocket flow."""

    async def _async_step_confirm(self) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        return await self.async_step_disable_outbound_websocket()

    async def async_step_disable_outbound_websocket(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        try:
            result = await self._device.ws_setconfig(
                False, self._device.config["ws"]["server"]
            )
            if result["restart_required"]:
                await self._device.trigger_reboot()
        except (DeviceConnectionError, RpcCallError):
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title="", data={})


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str] | None
) -> RepairsFlow:
    """Create flow."""
    if TYPE_CHECKING:
        assert isinstance(data, dict)

    entry_id = data["entry_id"]
    entry = hass.config_entries.async_get_entry(entry_id)

    if TYPE_CHECKING:
        assert entry is not None

    device = entry.runtime_data.rpc.device

    if (
        "ble_scanner_firmware_unsupported" in issue_id
        or "deprecated_firmware" in issue_id
    ):
        return FirmwareUpdateFlow(device)

    if "outbound_websocket_incorrectly_enabled" in issue_id:
        return DisableOutboundWebSocketFlow(device)

    return ConfirmRepairFlow()
