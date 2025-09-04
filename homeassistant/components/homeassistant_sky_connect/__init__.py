"""The Home Assistant SkyConnect integration."""

from __future__ import annotations

import logging
import os.path

from homeassistant.components.homeassistant_hardware.util import guess_firmware_info
from homeassistant.components.usb import (
    USBDevice,
    async_register_port_event_callback,
    scan_serial_ports,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    DESCRIPTION,
    DEVICE,
    DOMAIN,
    FIRMWARE,
    FIRMWARE_VERSION,
    MANUFACTURER,
    PID,
    PRODUCT,
    SERIAL_NUMBER,
    VID,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the ZBT-1 integration."""

    @callback
    def async_port_event_callback(
        added: set[USBDevice], removed: set[USBDevice]
    ) -> None:
        """Handle USB port events."""
        current_entries_by_path = {
            entry.data[DEVICE]: entry
            for entry in hass.config_entries.async_entries(DOMAIN)
        }

        for device in added | removed:
            path = device.device
            entry = current_entries_by_path.get(path)

            if entry is not None:
                _LOGGER.debug(
                    "Device %r has changed state, reloading config entry %s",
                    path,
                    entry,
                )
                hass.config_entries.async_schedule_reload(entry.entry_id)

    async_register_port_event_callback(hass, async_port_event_callback)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Home Assistant SkyConnect config entry."""

    # Postpone loading the config entry if the device is missing
    device_path = entry.data[DEVICE]
    if not await hass.async_add_executor_job(os.path.exists, device_path):
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_disconnected",
        )

    await hass.config_entries.async_forward_entry_setups(entry, ["update"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms(entry, ["update"])
    return True


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    _LOGGER.debug(
        "Migrating from version %s.%s", config_entry.version, config_entry.minor_version
    )

    if config_entry.version == 1:
        if config_entry.minor_version == 1:
            # Add-on startup with type service get started before Core, always (e.g. the
            # Multi-Protocol add-on). Probing the firmware would interfere with the add-on,
            # so we can't safely probe here. Instead, we must make an educated guess!
            firmware_guess = await guess_firmware_info(hass, config_entry.data[DEVICE])

            new_data = {**config_entry.data}
            new_data[FIRMWARE] = firmware_guess.firmware_type.value

            # Copy `description` to `product`
            new_data[PRODUCT] = new_data[DESCRIPTION]

            hass.config_entries.async_update_entry(
                config_entry,
                data=new_data,
                version=1,
                minor_version=2,
            )

        if config_entry.minor_version == 2:
            # Add a `firmware_version` key
            hass.config_entries.async_update_entry(
                config_entry,
                data={
                    **config_entry.data,
                    FIRMWARE_VERSION: None,
                },
                version=1,
                minor_version=3,
            )

        if config_entry.minor_version == 3:
            # Old SkyConnect config entries were missing keys
            if any(
                key not in config_entry.data
                for key in (VID, PID, MANUFACTURER, PRODUCT, SERIAL_NUMBER)
            ):
                serial_ports = await hass.async_add_executor_job(scan_serial_ports)
                serial_ports_info = {port.device: port for port in serial_ports}
                device = config_entry.data[DEVICE]

                if not (usb_info := serial_ports_info.get(device)):
                    raise HomeAssistantError(
                        f"USB device {device} is missing, cannot migrate"
                    )

                hass.config_entries.async_update_entry(
                    config_entry,
                    data={
                        **config_entry.data,
                        VID: usb_info.vid,
                        PID: usb_info.pid,
                        MANUFACTURER: usb_info.manufacturer,
                        PRODUCT: usb_info.description,
                        DESCRIPTION: usb_info.description,
                        SERIAL_NUMBER: usb_info.serial_number,
                    },
                    version=1,
                    minor_version=4,
                )
            else:
                # Existing entries are migrated by just incrementing the version
                hass.config_entries.async_update_entry(
                    config_entry,
                    version=1,
                    minor_version=4,
                )

        _LOGGER.debug(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
        )

        return True

    # This means the user has downgraded from a future version
    return False
