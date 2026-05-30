"""The Home Assistant Connect ZBT-2 integration."""

from dataclasses import dataclass
import logging
import os.path

from homeassistant.components.homeassistant_hardware.coordinator import (
    FirmwareUpdateCoordinator,
)
from homeassistant.components.usb import USBDevice, async_register_port_event_callback
from homeassistant.config_entries import SOURCE_IGNORE, ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import DEVICE, DOMAIN, NABU_CASA_FIRMWARE_RELEASES_URL, SERIAL_NUMBER

_LOGGER = logging.getLogger(__name__)

type HomeAssistantConnectZBT2ConfigEntry = ConfigEntry[HomeAssistantConnectZBT2Data]


@dataclass
class HomeAssistantConnectZBT2Data:
    """Runtime data definition."""

    coordinator: FirmwareUpdateCoordinator


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


async def async_setup_entry(
    hass: HomeAssistant, entry: HomeAssistantConnectZBT2ConfigEntry
) -> bool:
    """Set up a Home Assistant Connect ZBT-2 config entry."""

    # Postpone loading the config entry if the device is missing
    device_path = entry.data[DEVICE]
    if not await hass.async_add_executor_job(os.path.exists, device_path):
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="device_disconnected",
        )

    # Create and store the firmware update coordinator in runtime_data
    session = async_get_clientsession(hass)
    coordinator = FirmwareUpdateCoordinator(
        hass,
        entry,
        session,
        NABU_CASA_FIRMWARE_RELEASES_URL,
    )
    entry.runtime_data = HomeAssistantConnectZBT2Data(coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, ["switch", "update"])

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HomeAssistantConnectZBT2ConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, ["switch", "update"])


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: HomeAssistantConnectZBT2ConfigEntry
) -> bool:
    """Migrate old entry."""

    _LOGGER.debug(
        "Migrating from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 1:
        # This means the user has downgraded from a future version
        return False

    if config_entry.version == 1:
        if config_entry.minor_version == 1:
            serial_number = config_entry.data[SERIAL_NUMBER]

            # Installations ended up with multiple config entries per physical adapter
            # in 2026.5.0 and 2026.5.1. We need to delete the older entry.
            duplicates = [
                entry
                for entry in hass.config_entries.async_entries(DOMAIN)
                if entry.data.get(SERIAL_NUMBER) == serial_number
            ]
            canonical = max(
                duplicates,
                key=lambda e: (
                    e.source != SOURCE_IGNORE,
                    e.disabled_by is None,
                    e.minor_version,
                    e.modified_at,
                    e.entry_id,
                ),
            )

            if canonical.entry_id != config_entry.entry_id:
                # The canonical entry's migration will remove this duplicate.
                return False

            for duplicate in duplicates:
                if duplicate.entry_id == config_entry.entry_id:
                    continue
                _LOGGER.debug(
                    "Removing duplicate config entry %s for serial %s in favor of %s",
                    duplicate.entry_id,
                    serial_number,
                    config_entry.entry_id,
                )
                await hass.config_entries.async_remove(duplicate.entry_id)

            # Replace the synthetic unique ID with the USB serial number
            hass.config_entries.async_update_entry(
                config_entry,
                unique_id=serial_number,
                version=1,
                minor_version=2,
            )

        _LOGGER.debug(
            "Migration to version %s.%s successful",
            config_entry.version,
            config_entry.minor_version,
        )

        return True

    # This means the user has downgraded from a future version
    return False
