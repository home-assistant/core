"""The Broadlink integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .const import BROADLINK_DATA, DOMAIN, BroadlinkData
from .device import BroadlinkDevice
from .heartbeat import BroadlinkHeartbeat

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Broadlink integration."""
    hass.data[BROADLINK_DATA] = BroadlinkData()
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up a Broadlink device from a config entry."""
    data = hass.data[BROADLINK_DATA]

    device = BroadlinkDevice(hass, entry)
    if not await device.async_setup():
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="setup_failed",
            translation_placeholders={"host": entry.data[CONF_HOST]},
        )
    if data.heartbeat is None:
        data.heartbeat = BroadlinkHeartbeat(hass)
        hass.async_create_task(data.heartbeat.async_setup())


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""
    if entry.version > 1:
        return False

    if entry.minor_version < 2:
        # Hysen thermostats no longer provide time and select entities.
        entity_registry = er.async_get(hass)
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if entity_entry.domain in (Platform.SELECT, Platform.TIME):
                entity_registry.async_remove(entity_entry.entity_id)
        hass.config_entries.async_update_entry(entry, minor_version=2)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    data = hass.data[BROADLINK_DATA]

    device = data.devices.pop(entry.entry_id)
    result = await device.async_unload()

    if data.heartbeat and not data.devices:
        await data.heartbeat.async_unload()
        data.heartbeat = None

    if not result:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unload_failed",
        )
