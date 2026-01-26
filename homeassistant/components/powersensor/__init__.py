"""The Powersensor integration."""

import logging

from powersensor_local import VirtualHousehold

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.loader import async_get_integration

from .config_flow import PowersensorConfigFlow
from .const import (
    CFG_DEVICES,
    CFG_ROLES,
    DOMAIN,
    ROLE_SOLAR,
    RT_DISPATCHER,
    RT_VHH,
    RT_ZEROCONF,
)
from .PowersensorDiscoveryService import PowersensorDiscoveryService
from .PowersensorMessageDispatcher import PowersensorMessageDispatcher

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

#
# config entry.data structure (version 2.2):
#   {
#     devices = {
#       mac = {
#         name =,
#         display_name =,
#         mac =,
#         host =,
#         port =,
#     }
#     roles = {
#       mac = role,
#     }
#   }
#


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up integration from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}

    integration = await async_get_integration(hass, DOMAIN)
    manifest = integration.manifest

    try:
        # Establish create the zeroconf discovery service
        zeroconf_domain: str = str(manifest["zeroconf"][0])
        zeroconf_service = PowersensorDiscoveryService(hass, zeroconf_domain)
        await zeroconf_service.start()

        # Establish our virtual household
        with_solar = ROLE_SOLAR in entry.data.get(CFG_ROLES, {}).values()
        vhh = VirtualHousehold(with_solar)

        # Set up message dispatcher
        dispatcher = PowersensorMessageDispatcher(hass, entry, vhh)
        for network_info in entry.data.get(CFG_DEVICES, {}).values():
            await dispatcher.enqueue_plug_for_adding(network_info)
    except Exception as err:
        raise ConfigEntryNotReady(f"Unexpected error during setup: {err}") from err

    entry.runtime_data = {
        RT_VHH: vhh,
        RT_DISPATCHER: dispatcher,
        RT_ZEROCONF: zeroconf_service,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Started unloading for %s", entry.entry_id)
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if hasattr(entry, "runtime_data"):
            if RT_DISPATCHER in entry.runtime_data:
                await entry.runtime_data[RT_DISPATCHER].disconnect()
            if RT_ZEROCONF in entry.runtime_data:
                await entry.runtime_data[RT_ZEROCONF].stop()

    if entry.entry_id in hass.data[DOMAIN]:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old config entry."""
    _LOGGER.debug("Upgrading config from %s.%s", entry.version, entry.minor_version)
    if entry.version > PowersensorConfigFlow.VERSION:
        # Downgrade from future version
        return False

    if entry.version == 1:
        # Move device info into subkey
        devices = {**entry.data}
        new_data = {CFG_DEVICES: devices, CFG_ROLES: {}}
        hass.config_entries.async_update_entry(
            entry, data=new_data, version=2, minor_version=2
        )

    _LOGGER.debug("Upgrading config to %s.%s", entry.version, entry.minor_version)
    return True
