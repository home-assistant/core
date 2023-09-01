"""ZHA repairs for common environmental and device problems."""
from __future__ import annotations

import enum
import logging
from typing import Any, cast

from universal_silabs_flasher.const import ApplicationType
from universal_silabs_flasher.flasher import Flasher
from zigpy.backups import NetworkBackup

from homeassistant.components.homeassistant_sky_connect import (
    hardware as skyconnect_hardware,
)
from homeassistant.components.homeassistant_yellow import (
    RADIO_DEVICE as YELLOW_RADIO_DEVICE,
    hardware as yellow_hardware,
)
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from .core.const import DOMAIN
from .radio_manager import ZhaRadioManager

_LOGGER = logging.getLogger(__name__)


class AlreadyRunningEZSP(Exception):
    """The device is already running EZSP firmware."""


class HardwareType(enum.StrEnum):
    """Detected Zigbee hardware type."""

    SKYCONNECT = "skyconnect"
    YELLOW = "yellow"
    OTHER = "other"


DISABLE_MULTIPAN_URL = {
    HardwareType.YELLOW: (
        "https://yellow.home-assistant.io/guides/disable-multiprotocol/#flash-the-silicon-labs-radio-firmware"
    ),
    HardwareType.SKYCONNECT: (
        "https://skyconnect.home-assistant.io/procedures/disable-multiprotocol/#step-flash-the-silicon-labs-radio-firmware"
    ),
    HardwareType.OTHER: None,
}

ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED = "wrong_silabs_firmware_installed"
ISSUE_INCONSISTENT_NETWORK_SETTINGS = "inconsistent_network_settings"


def _detect_radio_hardware(hass: HomeAssistant, device: str) -> HardwareType:
    """Identify the radio hardware with the given serial port."""
    try:
        yellow_hardware.async_info(hass)
    except HomeAssistantError:
        pass
    else:
        if device == YELLOW_RADIO_DEVICE:
            return HardwareType.YELLOW

    try:
        info = skyconnect_hardware.async_info(hass)
    except HomeAssistantError:
        pass
    else:
        for hardware_info in info:
            for entry_id in hardware_info.config_entries or []:
                entry = hass.config_entries.async_get_entry(entry_id)

                if entry is not None and entry.data["device"] == device:
                    return HardwareType.SKYCONNECT

    return HardwareType.OTHER


async def probe_silabs_firmware_type(device: str) -> ApplicationType | None:
    """Probe the running firmware on a Silabs device."""
    flasher = Flasher(device=device)

    try:
        await flasher.probe_app_type()
    except Exception:  # pylint: disable=broad-except
        _LOGGER.debug("Failed to probe application type", exc_info=True)

    return flasher.app_type


async def warn_on_wrong_silabs_firmware(hass: HomeAssistant, device: str) -> bool:
    """Create a repair issue if the wrong type of SiLabs firmware is detected."""
    # Only consider actual serial ports
    if device.startswith("socket://"):
        return False

    app_type = await probe_silabs_firmware_type(device)

    if app_type is None:
        # Failed to probe, we can't tell if the wrong firmware is installed
        return False

    if app_type == ApplicationType.EZSP:
        # If connecting fails but we somehow probe EZSP (e.g. stuck in bootloader),
        # reconnect, it should work
        raise AlreadyRunningEZSP()

    hardware_type = _detect_radio_hardware(hass, device)
    ir.async_create_issue(
        hass,
        domain=DOMAIN,
        issue_id=ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED,
        is_fixable=False,
        is_persistent=True,
        learn_more_url=DISABLE_MULTIPAN_URL[hardware_type],
        severity=ir.IssueSeverity.ERROR,
        translation_key=(
            ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED
            + ("_nabucasa" if hardware_type != HardwareType.OTHER else "_other")
        ),
        translation_placeholders={"firmware_type": app_type.name},
    )

    return True


def _format_settings_diff(old_state: NetworkBackup, new_state: NetworkBackup) -> str:
    """Format the difference between two network backups."""
    lines: list[str] = []

    def _add_difference(
        lines: list[str], text: str, old: Any, new: Any, pre: bool = True
    ) -> None:
        """Add a line to the list if the values are different."""
        wrap = "`" if pre else ""

        if old != new:
            lines.append(f"{text}: {wrap}{old}{wrap} \u2192 {wrap}{new}{wrap}")

    _add_difference(
        lines,
        "Channel",
        old=old_state.network_info.channel,
        new=new_state.network_info.channel,
        pre=False,
    )
    _add_difference(
        lines,
        "Node IEEE",
        old=old_state.node_info.ieee,
        new=new_state.node_info.ieee,
    )
    _add_difference(
        lines,
        "PAN ID",
        old=old_state.network_info.pan_id,
        new=new_state.network_info.pan_id,
    )
    _add_difference(
        lines,
        "Extended PAN ID",
        old=old_state.network_info.extended_pan_id,
        new=new_state.network_info.extended_pan_id,
    )
    _add_difference(
        lines,
        "NWK update ID",
        old=old_state.network_info.nwk_update_id,
        new=new_state.network_info.nwk_update_id,
        pre=False,
    )
    _add_difference(
        lines,
        "TC Link Key",
        old=old_state.network_info.tc_link_key.key,
        new=new_state.network_info.tc_link_key.key,
    )
    _add_difference(
        lines,
        "Network Key",
        old=old_state.network_info.network_key.key,
        new=new_state.network_info.network_key.key,
    )

    return "\n".join([f"- {line}" for line in lines])


async def warn_on_inconsistent_network_settings(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    old_state: NetworkBackup,
    new_state: NetworkBackup,
) -> None:
    """Create a repair if the network settings are inconsistent with the last backup."""

    ir.async_create_issue(
        hass,
        domain=DOMAIN,
        issue_id=ISSUE_INCONSISTENT_NETWORK_SETTINGS,
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key=ISSUE_INCONSISTENT_NETWORK_SETTINGS,
        data={
            "config_entry_id": config_entry.entry_id,
            "old_state": old_state.as_dict(),
            "new_state": new_state.as_dict(),
        },
    )


def async_delete_blocking_issues(hass: HomeAssistant) -> None:
    """Delete repair issues that should disappear on a successful startup."""
    ir.async_delete_issue(hass, DOMAIN, ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED)
    ir.async_delete_issue(hass, DOMAIN, ISSUE_INCONSISTENT_NETWORK_SETTINGS)


class NetworkSettingsInconsistentFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, hass: HomeAssistant, data: dict[str, Any]) -> None:
        """Initialize the flow."""
        self.hass = hass
        self._old_state = NetworkBackup.from_dict(data["old_state"])
        self._new_state = NetworkBackup.from_dict(data["new_state"])

        self._entry_id: str = data["config_entry_id"]

        config_entry = self.hass.config_entries.async_get_entry(self._entry_id)
        assert config_entry is not None
        self._radio_mgr = ZhaRadioManager.from_config_entry(self.hass, config_entry)

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the first step of a fix flow."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["use_new_settings", "restore_old_settings"],
            description_placeholders={
                "diff": _format_settings_diff(self._old_state, self._new_state)
            },
        )

    async def async_step_use_new_settings(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Step to use the new settings found on the radio."""
        async with self._radio_mgr._connect_zigpy_app() as app:  # pylint: disable=protected-access
            await app.add_backup(self._new_state)

        await self.hass.config_entries.async_reload(self._entry_id)
        return self.async_create_entry(title="", data={})

    async def async_step_restore_old_settings(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Step to restore the most recent backup."""
        await self._radio_mgr.restore_backup(self._old_state)

        await self.hass.config_entries.async_reload(self._entry_id)
        return self.async_create_entry(title="", data={})


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id == ISSUE_INCONSISTENT_NETWORK_SETTINGS:
        return NetworkSettingsInconsistentFlow(hass, cast(dict[str, Any], data))

    return ConfirmRepairFlow()
