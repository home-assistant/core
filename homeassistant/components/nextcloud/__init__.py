"""The Nextcloud integration."""

import logging

from nextcloudmonitor import (
    NextcloudMonitor,
    NextcloudMonitorAuthorizationError,
    NextcloudMonitorConnectionError,
    NextcloudMonitorRequestError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN
from .coordinator import NextcloudDataUpdateCoordinator

PLATFORMS = (Platform.SENSOR, Platform.BINARY_SENSOR)

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Nextcloud integration."""

    # migrate old entity unique ids
    entity_reg = er.async_get(hass)
    entities: list[er.RegistryEntry] = er.async_entries_for_config_entry(
        entity_reg, entry.entry_id
    )
    for entity in entities:
        old_uid_start = f"{entry.data[CONF_URL]}#nextcloud_"
        new_uid_start = f"{entry.entry_id}#"
        if entity.unique_id.startswith(old_uid_start):
            new_uid = entity.unique_id.replace(old_uid_start, new_uid_start)
            _LOGGER.debug("migrate unique id '%s' to '%s'", entity.unique_id, new_uid)
            entity_reg.async_update_entity(entity.entity_id, new_unique_id=new_uid)

    def _connect_nc():
        return NextcloudMonitor(
            entry.data[CONF_URL],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_VERIFY_SSL],
        )

    try:
        ncm = await hass.async_add_executor_job(_connect_nc)
    except NextcloudMonitorAuthorizationError as ex:
        raise ConfigEntryAuthFailed from ex
    except (NextcloudMonitorConnectionError, NextcloudMonitorRequestError) as ex:
        raise ConfigEntryNotReady from ex

    coordinator = NextcloudDataUpdateCoordinator(
        hass,
        ncm,
        entry,
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Nextcloud integration."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok
