"""Utility functions for Home Assistant SkyConnect integration."""

from __future__ import annotations

from collections.abc import Iterable
import logging

from ha_silabs_firmware_client import FirmwareManifest, FirmwareMetadata

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.service_info.usb import UsbServiceInfo

from .const import HardwareVariant

_LOGGER = logging.getLogger(__name__)


def get_usb_service_info(config_entry: ConfigEntry) -> UsbServiceInfo:
    """Return UsbServiceInfo."""
    return UsbServiceInfo(
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


def get_supported_firmwares(manifest: FirmwareManifest) -> Iterable[FirmwareMetadata]:
    """Get a list of supported firmwares from a firmware update manifest."""
    return [
        fw
        for fw in manifest.firmwares
        if fw.filename.startswith(("skyconnect_", "zbt1_"))
    ]
