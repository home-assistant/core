"""The Home Assistant Connect ZBT-2 integration."""

from __future__ import annotations

import logging
import os.path

from homeassistant.components.usb import USBDevice, async_register_port_event_callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DEVICE, DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Home Assistant Connect ZBT-2 integration."""

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
    """Set up a Home Assistant Connect ZBT-2 config entry."""

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
