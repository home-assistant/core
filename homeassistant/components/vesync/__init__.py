"""VeSync integration."""

import logging

from pyvesync import VeSync

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .common import async_generate_device_list
from .const import (
    DOMAIN,
    SERVICE_UPDATE_DEVS,
    VS_COORDINATOR,
    VS_DEVICES,
    VS_DISCOVERY,
    VS_MANAGER,
)
from .coordinator import VeSyncDataCoordinator

PLATFORMS = [
    Platform.FAN,
    Platform.HUMIDIFIER,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Vesync as config entry."""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    time_zone = str(hass.config.time_zone)

    manager = VeSync(username, password, time_zone)

    login = await hass.async_add_executor_job(manager.login)

    if not login:
        _LOGGER.error("Unable to login to the VeSync server")
        return False

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_MANAGER] = manager

    coordinator = VeSyncDataCoordinator(hass, manager)

    # Store coordinator at domain level since only single integration instance is permitted.
    hass.data[DOMAIN][VS_COORDINATOR] = coordinator

    hass.data[DOMAIN][VS_DEVICES] = await async_generate_device_list(hass, manager)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    async def async_new_device_discovery(service: ServiceCall) -> None:
        """Discover if new devices should be added."""
        manager = hass.data[DOMAIN][VS_MANAGER]
        devices = hass.data[DOMAIN][VS_DEVICES]

        new_devices = await async_generate_device_list(hass, manager)

        device_set = set(new_devices)
        new_devices = list(device_set.difference(devices))
        if new_devices and devices:
            devices.extend(new_devices)
            async_dispatcher_send(hass, VS_DISCOVERY.format(VS_DEVICES), new_devices)
            return
        if new_devices and not devices:
            devices.extend(new_devices)

    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE_DEVS, async_new_device_discovery
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.pop(DOMAIN)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    if config_entry.version == 1:
        # Migrate switch/outlets entity to a new unique ID
        # How do we get unique id of the switch entity?
        entity_registry = await hass.helpers.entity_registry.async_get_registry()
        old_unique_ids = [
            entry.unique_id
            for entry in entity_registry.entities.values()
            if DOMAIN in entry.platform and "--" not in entry.unique_id
        ]

        for old_unique_id in old_unique_ids:
            new_unique_id = f"{old_unique_id}-device_status"
            entity_registry = await hass.helpers.entity_registry.async_get_registry()
            entity_entry = entity_registry.async_get(old_unique_id)
            if entity_entry:
                entity_registry.async_update_entity(
                    entity_entry.entity_id, new_unique_id=new_unique_id
                )
        hass.config_entries.async_update_entry(config_entry, version=2)
    return True
