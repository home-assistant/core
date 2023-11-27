"""The Ruckus Unleashed integration."""
import logging

from aioruckus import AjaxSession
from aioruckus.exceptions import AuthenticationError, SchemaError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import (
    API_AP_DEVNAME,
    API_AP_FIRMWAREVERSION,
    API_AP_MAC,
    API_AP_MODEL,
    API_SYS_SYSINFO,
    API_SYS_SYSINFO_VERSION,
    COORDINATOR,
    DOMAIN,
    MANUFACTURER,
    PLATFORMS,
    UNDO_UPDATE_LISTENERS,
)
from .coordinator import RuckusUnleashedDataUpdateCoordinator

_LOGGER = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ruckus Unleashed from a config entry."""

    ruckus = AjaxSession.async_create(
        entry.data[CONF_HOST],
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    try:
        await ruckus.login()
    except (ConnectionError, SchemaError) as conerr:
        await ruckus.close()
        raise ConfigEntryNotReady from conerr
    except AuthenticationError as autherr:
        await ruckus.close()
        raise ConfigEntryAuthFailed from autherr

    coordinator = RuckusUnleashedDataUpdateCoordinator(hass, ruckus=ruckus)

    await coordinator.async_config_entry_first_refresh()

    system_info = await ruckus.api.get_system_info()

    registry = dr.async_get(hass)
    aps = await ruckus.api.get_aps()
    for access_point in aps:
        _LOGGER.debug("AP [%s] %s", access_point[API_AP_MAC], entry.entry_id)
        registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections={(dr.CONNECTION_NETWORK_MAC, access_point[API_AP_MAC])},
            identifiers={(DOMAIN, access_point[API_AP_MAC])},
            manufacturer=MANUFACTURER,
            name=access_point[API_AP_DEVNAME],
            model=access_point[API_AP_MODEL],
            sw_version=access_point.get(
                API_AP_FIRMWAREVERSION,
                system_info[API_SYS_SYSINFO][API_SYS_SYSINFO_VERSION],
            ),
        )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
        UNDO_UPDATE_LISTENERS: [],
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        for listener in hass.data[DOMAIN][entry.entry_id][UNDO_UPDATE_LISTENERS]:
            listener()
        await hass.data[DOMAIN][entry.entry_id][COORDINATOR].ruckus.close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
