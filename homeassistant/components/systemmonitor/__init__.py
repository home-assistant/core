"""The System Monitor integration."""

from dataclasses import dataclass
import logging

import psutil_home_assistant as ha_psutil

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import SystemMonitorCoordinator
from .util import get_all_disk_mounts

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

type SystemMonitorConfigEntry = ConfigEntry[SystemMonitorData]


@dataclass
class SystemMonitorData:
    """Runtime data definition."""

    coordinator: SystemMonitorCoordinator
    psutil_wrapper: ha_psutil.PsutilWrapper


def _create_psutil_wrapper_and_get_disk_mounts(
    hass: HomeAssistant,
) -> tuple[ha_psutil.PsutilWrapper, set[str]]:
    """Create the psutil wrapper and return all disk mounts."""
    psutil_wrapper = ha_psutil.PsutilWrapper()
    return psutil_wrapper, get_all_disk_mounts(hass, psutil_wrapper)


async def async_setup_entry(
    hass: HomeAssistant, entry: SystemMonitorConfigEntry
) -> None:
    """Set up System Monitor from a config entry."""
    psutil_wrapper, disk_mounts = await hass.async_add_executor_job(
        _create_psutil_wrapper_and_get_disk_mounts, hass
    )
    disk_arguments = list(disk_mounts)
    legacy_resources: set[str] = set(entry.options.get("resources", []))
    for resource in legacy_resources:
        if resource.startswith("disk_"):
            split_index = resource.rfind("_")
            _type = resource[:split_index]
            argument = resource[split_index + 1 :]
            _LOGGER.debug("Loading legacy %s with argument %s", _type, argument)
            disk_arguments.append(argument)

    _LOGGER.debug("disk arguments to be added: %s", disk_arguments)

    coordinator: SystemMonitorCoordinator = SystemMonitorCoordinator(
        hass,
        entry,
        psutil_wrapper,
        disk_arguments,
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = SystemMonitorData(coordinator, psutil_wrapper)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: SystemMonitorConfigEntry
) -> None:
    """Unload System Monitor config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: SystemMonitorConfigEntry
) -> None:
    """Migrate old entry."""

    if entry.version == 1 and entry.minor_version < 3:
        new_options = {**entry.options}
        if entry.minor_version == 1:
            # Migration copies process sensors to binary sensors
            # Repair will remove sensors when user submit the fix
            if processes := entry.options.get(SENSOR_DOMAIN):
                new_options[BINARY_SENSOR_DOMAIN] = processes
        hass.config_entries.async_update_entry(
            entry, options=new_options, version=1, minor_version=2
        )

        if entry.minor_version == 2:
            new_options = {**entry.options}
            if SENSOR_DOMAIN in new_options:
                new_options.pop(SENSOR_DOMAIN)
            hass.config_entries.async_update_entry(
                entry, options=new_options, version=1, minor_version=3
            )

    _LOGGER.debug(
        "Migration to version %s.%s successful", entry.version, entry.minor_version
    )
