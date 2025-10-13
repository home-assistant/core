"""VeSync integration."""

import logging

from pyvesync import VeSync
from pyvesync.utils.errors import VeSyncLoginError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, SERVICE_UPDATE_DEVS, VS_COORDINATOR, VS_MANAGER
from .coordinator import VeSyncDataCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.FAN,
    Platform.HUMIDIFIER,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Vesync as config entry."""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    time_zone = str(hass.config.time_zone)

    manager = VeSync(
        username=username,
        password=password,
        time_zone=time_zone,
        session=async_get_clientsession(hass),
    )
    try:
        await manager.login()
    except VeSyncLoginError as err:
        raise ConfigEntryAuthFailed from err

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][VS_MANAGER] = manager

    coordinator = VeSyncDataCoordinator(hass, config_entry, manager)

    # Store coordinator at domain level since only single integration instance is permitted.
    hass.data[DOMAIN][VS_COORDINATOR] = coordinator
    await manager.update()
    await manager.check_firmware()

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    async def async_new_device_discovery(service: ServiceCall) -> None:
        """Discover and add new devices."""
        manager = hass.data[DOMAIN][VS_MANAGER]
        known_devices = list(manager.devices)
        await manager.get_devices()
        new_devices = [
            device for device in manager.devices if device not in known_devices
        ]

        if new_devices:
            async_dispatcher_send(hass, "vesync_new_devices", new_devices)

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
    _LOGGER.debug(
        "Migrating VeSync config entry: %s minor version: %s",
        config_entry.version,
        config_entry.minor_version,
    )
    if config_entry.minor_version == 1:
        # Migrate switch/outlets entity to a new unique ID
        _LOGGER.debug("Migrating VeSync config entry from version 1 to version 2")
        entity_registry = er.async_get(hass)
        registry_entries = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        for reg_entry in registry_entries:
            if "-" not in reg_entry.unique_id and reg_entry.entity_id.startswith(
                Platform.SWITCH
            ):
                _LOGGER.debug(
                    "Migrating switch/outlet entity from unique_id: %s to unique_id: %s",
                    reg_entry.unique_id,
                    reg_entry.unique_id + "-device_status",
                )
                entity_registry.async_update_entity(
                    reg_entry.entity_id,
                    new_unique_id=reg_entry.unique_id + "-device_status",
                )
            else:
                _LOGGER.debug("Skipping entity with unique_id: %s", reg_entry.unique_id)
        hass.config_entries.async_update_entry(config_entry, minor_version=2)

    return True
