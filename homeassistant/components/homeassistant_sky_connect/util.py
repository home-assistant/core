"""Utility functions for Home Assistant SkyConnect integration."""

from __future__ import annotations

import logging
from typing import cast

from universal_silabs_flasher.const import ApplicationType

from homeassistant.components import usb
from homeassistant.components.hassio import (
    AddonError,
    AddonManager,
    AddonState,
    is_hassio,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import ZHA_DOMAIN, HardwareVariant

_LOGGER = logging.getLogger(__name__)


def get_usb_service_info(config_entry: ConfigEntry) -> usb.UsbServiceInfo:
    """Return UsbServiceInfo."""
    return usb.UsbServiceInfo(
        device=config_entry.data["device"],
        vid=config_entry.data["vid"],
        pid=config_entry.data["pid"],
        serial_number=config_entry.data["serial_number"],
        manufacturer=config_entry.data["manufacturer"],
        description=config_entry.data["description"],
    )


def get_hardware_variant(config_entry: ConfigEntry) -> HardwareVariant:
    """Get the hardware variant from the config entry."""
    return HardwareVariant.from_usb_product_name(config_entry.data["description"])


def get_zha_device_path(config_entry: ConfigEntry) -> str:
    """Get the device path from a ZHA config entry."""
    return cast(str, config_entry.data["device"]["path"])


async def guess_firmware_type(hass: HomeAssistant, device_path: str) -> ApplicationType:
    """Guess the firmware type based on installed addons and other integrations."""
    device_guesses: dict[str | None, ApplicationType] = {}

    for zha_config_entry in hass.config_entries.async_entries(ZHA_DOMAIN):
        zha_path = get_zha_device_path(zha_config_entry)
        device_guesses[zha_path] = ApplicationType.EZSP

    if is_hassio(hass):
        otbr_addon_manager = AddonManager(
            hass=hass,
            logger=_LOGGER,
            addon_name="OpenThread Border Router",
            addon_slug="core_openthread_border_router",
        )

        try:
            otbr_addon_info = await otbr_addon_manager.async_get_addon_info()
        except AddonError:
            pass
        else:
            if otbr_addon_info.state != AddonState.NOT_INSTALLED:
                otbr_path = otbr_addon_info.options.get("device")
                device_guesses[otbr_path] = ApplicationType.SPINEL

        multipan_addon_manager = AddonManager(
            hass=hass,
            logger=_LOGGER,
            addon_name="Silicon Labs Multiprotocol",
            addon_slug="core_silabs_multiprotocol",
        )

        try:
            multipan_addon_info = await multipan_addon_manager.async_get_addon_info()
        except AddonError:
            pass
        else:
            if multipan_addon_info.state != AddonState.NOT_INSTALLED:
                multipan_path = multipan_addon_info.options.get("device")
                device_guesses[multipan_path] = ApplicationType.CPC

    # Fall back to EZSP if we can't guess the firmware type
    return device_guesses.get(device_path, ApplicationType.EZSP)
