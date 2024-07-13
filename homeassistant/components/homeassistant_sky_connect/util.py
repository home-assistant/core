"""Utility functions for Home Assistant SkyConnect integration."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import logging
from typing import cast

from universal_silabs_flasher.const import ApplicationType

from homeassistant.components import usb
from homeassistant.components.hassio import AddonError, AddonState, is_hassio
from homeassistant.components.homeassistant_hardware.silabs_multiprotocol_addon import (
    WaitingAddonManager,
    get_multiprotocol_addon_manager,
)
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import (
    OTBR_ADDON_MANAGER_DATA,
    OTBR_ADDON_NAME,
    OTBR_ADDON_SLUG,
    ZHA_DOMAIN,
    ZIGBEE_FLASHER_ADDON_MANAGER_DATA,
    ZIGBEE_FLASHER_ADDON_NAME,
    ZIGBEE_FLASHER_ADDON_SLUG,
    HardwareVariant,
)

_LOGGER = logging.getLogger(__name__)


def get_usb_service_info(config_entry: ConfigEntry) -> usb.UsbServiceInfo:
    """Return UsbServiceInfo."""
    return usb.UsbServiceInfo(
        device=config_entry.data["device"],
        vid=config_entry.data["vid"],
        pid=config_entry.data["pid"],
        serial_number=config_entry.data["serial_number"],
        manufacturer=config_entry.data["manufacturer"],
        description=config_entry.data["product"],
    )


def get_hardware_variant(config_entry: ConfigEntry) -> HardwareVariant:
    """Get the hardware variant from the config entry."""
    return HardwareVariant.from_usb_product_name(config_entry.data["product"])


def get_zha_device_path(config_entry: ConfigEntry) -> str | None:
    """Get the device path from a ZHA config entry."""
    return cast(str | None, config_entry.data.get("device", {}).get("path", None))


@singleton(OTBR_ADDON_MANAGER_DATA)
@callback
def get_otbr_addon_manager(hass: HomeAssistant) -> WaitingAddonManager:
    """Get the OTBR add-on manager."""
    return WaitingAddonManager(
        hass,
        _LOGGER,
        OTBR_ADDON_NAME,
        OTBR_ADDON_SLUG,
    )


@singleton(ZIGBEE_FLASHER_ADDON_MANAGER_DATA)
@callback
def get_zigbee_flasher_addon_manager(hass: HomeAssistant) -> WaitingAddonManager:
    """Get the flasher add-on manager."""
    return WaitingAddonManager(
        hass,
        _LOGGER,
        ZIGBEE_FLASHER_ADDON_NAME,
        ZIGBEE_FLASHER_ADDON_SLUG,
    )


@dataclass(slots=True, kw_only=True)
class FirmwareGuess:
    """Firmware guess."""

    is_running: bool
    firmware_type: ApplicationType
    source: str


async def guess_firmware_type(hass: HomeAssistant, device_path: str) -> FirmwareGuess:
    """Guess the firmware type based on installed addons and other integrations."""
    device_guesses: defaultdict[str | None, list[FirmwareGuess]] = defaultdict(list)

    for zha_config_entry in hass.config_entries.async_entries(ZHA_DOMAIN):
        zha_path = get_zha_device_path(zha_config_entry)

        if zha_path is not None:
            device_guesses[zha_path].append(
                FirmwareGuess(
                    is_running=(zha_config_entry.state == ConfigEntryState.LOADED),
                    firmware_type=ApplicationType.EZSP,
                    source="zha",
                )
            )

    if is_hassio(hass):
        otbr_addon_manager = get_otbr_addon_manager(hass)

        try:
            otbr_addon_info = await otbr_addon_manager.async_get_addon_info()
        except AddonError:
            pass
        else:
            if otbr_addon_info.state != AddonState.NOT_INSTALLED:
                otbr_path = otbr_addon_info.options.get("device")
                device_guesses[otbr_path].append(
                    FirmwareGuess(
                        is_running=(otbr_addon_info.state == AddonState.RUNNING),
                        firmware_type=ApplicationType.SPINEL,
                        source="otbr",
                    )
                )

        multipan_addon_manager = await get_multiprotocol_addon_manager(hass)

        try:
            multipan_addon_info = await multipan_addon_manager.async_get_addon_info()
        except AddonError:
            pass
        else:
            if multipan_addon_info.state != AddonState.NOT_INSTALLED:
                multipan_path = multipan_addon_info.options.get("device")
                device_guesses[multipan_path].append(
                    FirmwareGuess(
                        is_running=(multipan_addon_info.state == AddonState.RUNNING),
                        firmware_type=ApplicationType.CPC,
                        source="multiprotocol",
                    )
                )

    # Fall back to EZSP if we can't guess the firmware type
    if device_path not in device_guesses:
        return FirmwareGuess(
            is_running=False, firmware_type=ApplicationType.EZSP, source="unknown"
        )

    # Prioritizes guesses that were pulled from a running addon or integration but keep
    # the sort order we defined above
    guesses = sorted(
        device_guesses[device_path],
        key=lambda guess: guess.is_running,
    )

    assert guesses

    return guesses[-1]
