"""The Ruckus integration."""

import logging

from aioruckus import AjaxSession
from aioruckus.exceptions import AuthenticationError, SchemaError

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
    DOMAIN,
    MANUFACTURER,
    PLATFORMS,
)
from .coordinator import RuckusDataUpdateCoordinator, RuckusUnleashedConfigEntry

_LOGGER = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, entry: RuckusUnleashedConfigEntry
) -> bool:
    """Set up Ruckus from a config entry."""

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

    coordinator = RuckusDataUpdateCoordinator(hass, entry, ruckus)

    try:
        await coordinator.async_config_entry_first_refresh()

        system_info = await ruckus.api.get_system_info()
        aps = await ruckus.api.get_aps()
    except ConfigEntryNotReady, ConfigEntryAuthFailed, ConnectionError, SchemaError:
        await ruckus.close()
        raise

    registry = dr.async_get(hass)
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

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: RuckusUnleashedConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.ruckus.close()
    return unload_ok
