"""The Home Assistant SkyConnect integration."""

from __future__ import annotations

import logging
import os.path

from homeassistant.components.homeassistant_hardware.util import guess_firmware_info
from homeassistant.components.usb import USBDevice, async_register_port_event_callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DESCRIPTION, DEVICE, FIRMWARE, FIRMWARE_VERSION, PRODUCT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Home Assistant SkyConnect config entry."""

    # Postpone loading the config entry if the device is missing
    device_path = entry.data[DEVICE]
    if not await hass.async_add_executor_job(os.path.exists, device_path):
        raise ConfigEntryNotReady

    @callback
    def async_port_event_callback(
        added: set[USBDevice], removed: set[USBDevice]
    ) -> None:
        """Handle USB port events."""
        if not added and not removed:
            return

        for device in removed:
            if device.device == device_path:
                _LOGGER.debug(
                    "Device %r has been unplugged, reloading config entry",
                    device.device,
                )
                hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))
                return

    # Handle the ZBT-1 being unplugged
    entry.async_on_unload(
        async_register_port_event_callback(hass, async_port_event_callback)
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
        "Migrating from version %s:%s", config_entry.version, config_entry.minor_version
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

        _LOGGER.debug(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
        )

        return True

    # This means the user has downgraded from a future version
    return False
