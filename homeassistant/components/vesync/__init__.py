"""VeSync integration."""

import logging

from pyvesync import VeSync
from pyvesync.utils.errors import (
    VeSyncAPIResponseError,
    VeSyncLoginError,
    VeSyncServerError,
)

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import VesyncConfigEntry, VeSyncDataCoordinator
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up my integration."""

    async_setup_services(hass)

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: VesyncConfigEntry
) -> bool:
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
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from err
    except VeSyncServerError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="server_error"
        ) from err
    except VeSyncAPIResponseError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="api_response_error"
        ) from err

    await manager.update()
    await manager.check_firmware()

    config_entry.runtime_data = VeSyncDataCoordinator(hass, config_entry, manager)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: VesyncConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: VesyncConfigEntry
) -> bool:
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


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: VesyncConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    manager = config_entry.runtime_data.manager
    await manager.get_devices()
    for dev in manager.devices:
        if isinstance(dev.sub_device_no, int):
            device_id = f"{dev.cid}{dev.sub_device_no!s}"
        else:
            device_id = dev.cid
        identifier = next(iter(device_entry.identifiers), None)
        if identifier and device_id == identifier[1]:
            return False

    return True
