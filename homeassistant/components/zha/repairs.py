"""ZHA repairs for common environmental and device problems."""
from __future__ import annotations

import enum

from universal_silabs_flasher.const import ApplicationType
from universal_silabs_flasher.flasher import Flasher

from homeassistant.components.homeassistant_sky_connect import (
    hardware as skyconnect_hardware,
)
from homeassistant.components.homeassistant_yellow import (
    RADIO_DEVICE as YELLOW_RADIO_DEVICE,
    hardware as yellow_hardware,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import issue_registry as ir

from .core.const import DOMAIN


class HardwareType(enum.StrEnum):
    """Detected Zigbee hardware type."""

    SKYCONNECT = "skyconnect"
    YELLOW = "yellow"
    OTHER = "other"


DISABLE_MULTIPAN_URL = {
    HardwareType.YELLOW: (
        "https://yellow.home-assistant.io/guides/disable-multiprotocol/"
    ),
    HardwareType.SKYCONNECT: (
        "https://skyconnect.home-assistant.io/procedures/disable-multiprotocol/"
    ),
    HardwareType.OTHER: None,
}

ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED = "wrong_silabs_firmware_installed"


def detect_radio_hardware(hass: HomeAssistant, device: str) -> HardwareType:
    """Identify the radio hardware with the given serial port."""
    try:
        info = yellow_hardware.async_info(hass)
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
    await flasher.probe_app_type()

    return flasher.app_type


async def warn_on_wrong_silabs_firmware(hass: HomeAssistant, device: str) -> None:
    """Create a repair issue if the wrong type of SiLabs firmware is detected."""
    app_type = await probe_silabs_firmware_type(device)

    if app_type is None:
        # Failed to probe, we can't tell if the wrong firmware is installed
        return

    if app_type == ApplicationType.EZSP:
        # If connecting fails but we somehow probe EZSP (e.g. stuck in bootloader),
        # reconnect, it should work
        raise ConfigEntryNotReady()

    hardware_type = detect_radio_hardware(hass, device)
    ir.async_create_issue(
        hass,
        domain=DOMAIN,
        issue_id=ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED,
        is_fixable=False,
        is_persistent=False,
        learn_more_url=DISABLE_MULTIPAN_URL[hardware_type],
        severity=ir.IssueSeverity.CRITICAL,
        translation_key=(
            ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED
            + ("_nabucasa" if hardware_type != HardwareType.OTHER else "_other")
        ),
        translation_placeholders={"firmware_type": app_type.name},
    )


def async_delete_blocking_issues(hass: HomeAssistant) -> None:
    """Delete repair issues that should disappear on a successful startup."""
    ir.async_delete_issue(hass, DOMAIN, ISSUE_WRONG_SILABS_FIRMWARE_INSTALLED)
