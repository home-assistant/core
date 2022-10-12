"""The keenetic_ndms2 component."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry, entity_registry

from .const import (
    CONF_CONSIDER_HOME,
    CONF_INCLUDE_ARP,
    CONF_INCLUDE_ASSOCIATED,
    CONF_INTERFACES,
    CONF_TRY_HOTSPOT,
    DEFAULT_CONSIDER_HOME,
    DEFAULT_INTERFACE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ROUTER,
    UNDO_UPDATE_LISTENER,
)
from .router import KeeneticRouter

PLATFORMS = [Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the component."""
    hass.data.setdefault(DOMAIN, {})
    async_add_defaults(hass, entry)

    router = KeeneticRouter(hass, entry)
    await router.async_setup()

    undo_listener = entry.add_update_listener(update_listener)

    hass.data[DOMAIN][entry.entry_id] = {
        ROUTER: router,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN][config_entry.entry_id][UNDO_UPDATE_LISTENER]()

    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    router: KeeneticRouter = hass.data[DOMAIN][config_entry.entry_id][ROUTER]

    await router.async_teardown()

    hass.data[DOMAIN].pop(config_entry.entry_id)

    new_tracked_interfaces: set[str] = set(config_entry.options[CONF_INTERFACES])

    if router.tracked_interfaces - new_tracked_interfaces:
        _LOGGER.debug(
            "Cleaning device_tracker entities since some interfaces are now untracked:"
        )
        ent_reg = entity_registry.async_get(hass)
        dev_reg = device_registry.async_get(hass)
        # We keep devices currently connected to new_tracked_interfaces
        keep_devices: set[str] = {
            mac
            for mac, device in router.last_devices.items()
            if device.interface in new_tracked_interfaces
        }
        for entity_entry in list(ent_reg.entities.values()):
            if (
                entity_entry.config_entry_id == config_entry.entry_id
                and entity_entry.domain == Platform.DEVICE_TRACKER
            ):
                mac = entity_entry.unique_id.partition("_")[0]
                if mac not in keep_devices:
                    _LOGGER.debug("Removing entity %s", entity_entry.entity_id)

                    ent_reg.async_remove(entity_entry.entity_id)
                    if entity_entry.device_id:
                        dev_reg.async_update_device(
                            entity_entry.device_id,
                            remove_config_entry_id=config_entry.entry_id,
                        )

        _LOGGER.debug("Finished cleaning device_tracker entities")

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def async_add_defaults(hass: HomeAssistant, entry: ConfigEntry):
    """Populate default options."""
    host: str = entry.data[CONF_HOST]
    imported_options: dict = hass.data[DOMAIN].get(f"imported_options_{host}", {})
    options = {
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        CONF_CONSIDER_HOME: DEFAULT_CONSIDER_HOME,
        CONF_INTERFACES: [DEFAULT_INTERFACE],
        CONF_TRY_HOTSPOT: True,
        CONF_INCLUDE_ARP: True,
        CONF_INCLUDE_ASSOCIATED: True,
        **imported_options,
        **entry.options,
    }

    if options.keys() - entry.options.keys():
        hass.config_entries.async_update_entry(entry, options=options)
