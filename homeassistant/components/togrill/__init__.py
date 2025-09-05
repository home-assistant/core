"""The ToGrill integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_ACTIVE_BY_DEFAULT, MAJOR_VERSION, MINOR_VERSION
from .coordinator import LOGGER, DeviceNotFound, ToGrillConfigEntry, ToGrillCoordinator

_PLATFORMS: list[Platform] = [
    Platform.EVENT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ToGrillConfigEntry) -> bool:
    """Set up ToGrill Bluetooth from a config entry."""

    coordinator = ToGrillCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as exc:
        if not isinstance(exc.__cause__, DeviceNotFound):
            raise

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ToGrillConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ToGrillConfigEntry
) -> bool:
    """Migrate old entry."""

    LOGGER.debug(
        "Migrating from version %s.%s", config_entry.version, config_entry.minor_version
    )

    if config_entry.version == 1 and config_entry.minor_version == 1:
        hass.config_entries.async_update_entry(
            config_entry,
            options={**config_entry.options, CONF_ACTIVE_BY_DEFAULT: True},
            version=1,
            minor_version=2,
        )

    return (
        config_entry.version == MAJOR_VERSION
        and config_entry.minor_version == MINOR_VERSION
    )
