"""Repairs flow for Shelly."""

from typing import TYPE_CHECKING, override

from aioshelly.block_device import BlockDevice
from aioshelly.const import MODEL_OUT_PLUG_S_G3, MODEL_PLUG_S_G3, RPC_GENERATIONS
from aioshelly.exceptions import DeviceConnectionError, RpcCallError
from aioshelly.rpc_device import RpcDevice
from awesomeversion import AwesomeVersion
import voluptuous as vol

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir

from .const import (
    BLE_SCANNER_FIRMWARE_UNSUPPORTED_ISSUE_ID,
    BLE_SCANNER_MIN_FIRMWARE,
    CONF_BLE_SCANNER_MODE,
    DEPRECATED_FIRMWARE_ISSUE_ID,
    DEPRECATED_FIRMWARES,
    DOMAIN,
    OPEN_WIFI_AP_ISSUE_ID,
    OUTBOUND_WEBSOCKET_INCORRECTLY_ENABLED_ISSUE_ID,
    BLEScannerMode,
)
from .coordinator import ShellyConfigEntry
from .utils import (
    get_coiot_address,
    get_coiot_port,
    get_device_entry_gen,
    get_rpc_ws_url,
)


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
        if firmware < BLE_SCANNER_MIN_FIRMWARE and entry.options.get(
            CONF_BLE_SCANNER_MODE
        ) in (BLEScannerMode.ACTIVE, BLEScannerMode.AUTO):
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
) -> None:
    """Manage deprecated firmware issue."""
    issue_id = DEPRECATED_FIRMWARE_ISSUE_ID.format(unique=entry.unique_id)

    if TYPE_CHECKING:
        assert entry.runtime_data.rpc is not None

    device = entry.runtime_data.rpc.device
    model = entry.data["model"]

    if model in DEPRECATED_FIRMWARES:
        min_firmware = DEPRECATED_FIRMWARES[model]["min_firmware"]
        ha_version = DEPRECATED_FIRMWARES[model]["ha_version"]

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

    if not device.initialized:
        return

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


@callback
def async_manage_open_wifi_ap_issue(
    hass: HomeAssistant,
    entry: ShellyConfigEntry,
) -> None:
    """Manage the open WiFi AP issue."""
    issue_id = OPEN_WIFI_AP_ISSUE_ID.format(unique=entry.unique_id)

    if TYPE_CHECKING:
        assert entry.runtime_data.rpc is not None

    device = entry.runtime_data.rpc.device

    if not device.initialized:
        return

    # Check if WiFi AP is enabled and is open (no password)
    if (
        (wifi_config := device.config.get("wifi"))
        and (ap_config := wifi_config.get("ap"))
        and ap_config.get("enable")
        and ap_config.get("is_open")
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=True,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="open_wifi_ap",
            translation_placeholders={
                "device_name": device.name,
                "ip_address": device.ip_address,
            },
            data={"entry_id": entry.entry_id},
        )
        return

    ir.async_delete_issue(hass, DOMAIN, issue_id)


class ShellyBlockRepairsFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, device: BlockDevice) -> None:
        """Initialize."""
        self._device = device


class CoiotConfigureFlow(ShellyBlockRepairsFlow):
    """Handler for fixing CoIoT configuration flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        issue_registry = ir.async_get(self.hass)
        description_placeholders = None
        if issue := issue_registry.async_get_issue(DOMAIN, self.issue_id):
            description_placeholders = issue.translation_placeholders

        return self.async_show_menu(
            menu_options=["confirm", "ignore"],
            description_placeholders=description_placeholders,
        )

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        coiot_addr = await get_coiot_address(self.hass)
        coiot_port = get_coiot_port(self.hass)
        if coiot_addr is None or coiot_port is None:
            return self.async_abort(reason="cannot_configure")
        try:
            await self._device.configure_coiot_protocol(coiot_addr, coiot_port)
            await self._device.trigger_reboot()
        except DeviceConnectionError:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title="", data={})

    async def async_step_ignore(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the ignore step of a fix flow."""
        ir.async_ignore_issue(self.hass, DOMAIN, self.issue_id, True)
        return self.async_abort(reason="issue_ignored")


class ShellyRpcRepairsFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, device: RpcDevice) -> None:
        """Initialize."""
        self._device = device

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
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

    async def _async_step_confirm(self) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        raise NotImplementedError


class FirmwareUpdateFlow(ShellyRpcRepairsFlow):
    """Handler for Firmware Update flow."""

    @override
    async def _async_step_confirm(self) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        return await self.async_step_update_firmware()

    async def async_step_update_firmware(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        if not self._device.status["sys"]["available_updates"]:
            return self.async_abort(reason="update_not_available")
        try:
            await self._device.trigger_ota_update()
        except DeviceConnectionError, RpcCallError:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title="", data={})


class DisableOutboundWebSocketFlow(ShellyRpcRepairsFlow):
    """Handler for Disable Outbound WebSocket flow."""

    @override
    async def _async_step_confirm(self) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        return await self.async_step_disable_outbound_websocket()

    async def async_step_disable_outbound_websocket(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        try:
            result = await self._device.ws_setconfig(
                False, self._device.config["ws"]["server"]
            )
            if result["restart_required"]:
                await self._device.trigger_reboot()
        except DeviceConnectionError, RpcCallError:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title="", data={})


class DisableOpenWiFiApFlow(RepairsFlow):
    """Handler for Disable Open WiFi AP flow."""

    def __init__(self, device: RpcDevice, issue_id: str) -> None:
        """Initialize."""
        self._device = device
        self.issue_id = issue_id

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        issue_registry = ir.async_get(self.hass)
        description_placeholders = None
        if issue := issue_registry.async_get_issue(DOMAIN, self.issue_id):
            description_placeholders = issue.translation_placeholders

        return self.async_show_menu(
            menu_options=["confirm", "ignore"],
            description_placeholders=description_placeholders,
        )

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        try:
            result = await self._device.wifi_setconfig(ap_enable=False)
            if result.get("restart_required"):
                await self._device.trigger_reboot()
        except DeviceConnectionError, RpcCallError:
            return self.async_abort(reason="cannot_connect")

        return self.async_create_entry(title="", data={})

    async def async_step_ignore(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the ignore step of a fix flow."""
        ir.async_ignore_issue(self.hass, DOMAIN, self.issue_id, True)
        return self.async_abort(reason="issue_ignored")


class DeviceConflictRepairFlow(RepairsFlow):
    """Handler for fixing a device conflict (hardware replacement)."""

    def __init__(self, data: dict[str, str]) -> None:
        """Initialize."""
        self._data = data

    @property
    def entry_id(self) -> str:
        """Return the config entry id to migrate."""
        return self._data["entry_id"]

    @property
    def old_mac(self) -> str:
        """Return the stored MAC address of the old device."""
        return self._data["old_mac"]

    @property
    def new_mac(self) -> str:
        """Return the MAC address of the new device."""
        return self._data["new_mac"]

    @callback
    def _description_placeholders(self) -> dict[str, str] | None:
        """Return the issue's translation placeholders."""
        issue_registry = ir.async_get(self.hass)
        if issue := issue_registry.async_get_issue(DOMAIN, self.issue_id):
            return issue.translation_placeholders
        return None

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return self.async_show_menu(
            menu_options=["migrate", "manual"],
            description_placeholders=self._description_placeholders(),
        )

    async def async_step_migrate(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the migrate step of a fix flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="migrate",
                data_schema=vol.Schema({}),
                description_placeholders=self._description_placeholders(),
            )

        # Imported here to avoid a circular import (__init__ imports repairs).
        from . import async_replace_device  # noqa: PLC0415

        await async_replace_device(self.hass, self.entry_id, self.old_mac, self.new_mac)
        self.hass.config_entries.async_schedule_reload(self.entry_id)
        return self.async_create_entry(title="", data={})

    async def async_step_manual(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the manual step of a fix flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema({}),
                description_placeholders=self._description_placeholders(),
            )

        # The user resolved the conflict on the hardware side (removed or
        # renamed the duplicate). Reload so a clean connect clears the issue.
        self.hass.config_entries.async_schedule_reload(self.entry_id)
        return self.async_create_entry(title="", data={})


async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict[str, str] | None
) -> RepairsFlow:
    """Create flow."""
    if TYPE_CHECKING:
        assert isinstance(data, dict)

    # A device conflict repair must be routed before the live-device lookup
    # below: during a hardware swap the entry may have no live device object
    # at all (it can be in ConfigEntryNotReady), so runtime_data.rpc/block
    # would not be set. The conflict flow needs only the issue data.
    if "device_conflict" in issue_id:
        return DeviceConflictRepairFlow(data)

    entry_id = data["entry_id"]
    entry = hass.config_entries.async_get_entry(entry_id)

    if TYPE_CHECKING:
        assert entry is not None

    if get_device_entry_gen(entry) in RPC_GENERATIONS:
        device = entry.runtime_data.rpc.device
    else:
        device = entry.runtime_data.block.device

    if "coiot_unconfigured" in issue_id:
        return CoiotConfigureFlow(device)

    if (
        "ble_scanner_firmware_unsupported" in issue_id
        or "deprecated_firmware" in issue_id
    ):
        return FirmwareUpdateFlow(device)

    if "outbound_websocket_incorrectly_enabled" in issue_id:
        return DisableOutboundWebSocketFlow(device)

    if "open_wifi_ap" in issue_id:
        return DisableOpenWiFiApFlow(device, issue_id)

    return ConfirmRepairFlow()
