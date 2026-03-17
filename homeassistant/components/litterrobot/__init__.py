"""The Litter-Robot integration."""

from __future__ import annotations

import itertools
import logging

from pylitterbot import Account
from pylitterbot.exceptions import LitterRobotException

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import LitterRobotConfigEntry, LitterRobotDataUpdateCoordinator
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
    Platform.UPDATE,
    Platform.VACUUM,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_migrate_entry(
    hass: HomeAssistant, entry: LitterRobotConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        entry.version,
        entry.minor_version,
    )

    if entry.version > 1:
        return False

    if entry.minor_version < 2:
        account = Account(websession=async_get_clientsession(hass))
        try:
            await account.connect(
                username=entry.data[CONF_USERNAME],
                password=entry.data[CONF_PASSWORD],
            )
            user_id = account.user_id
        except LitterRobotException:
            _LOGGER.debug("Could not connect to set unique_id during migration")
            return False
        finally:
            await account.disconnect()

        if user_id and not hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, user_id
        ):
            hass.config_entries.async_update_entry(
                entry, unique_id=user_id, minor_version=2
            )
        else:
            hass.config_entries.async_update_entry(entry, minor_version=2)

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        entry.version,
        entry.minor_version,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: LitterRobotConfigEntry) -> bool:
    """Set up Litter-Robot from a config entry."""
    coordinator = LitterRobotDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: LitterRobotConfigEntry
) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.account.disconnect()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: LitterRobotConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device."""
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        for _id in itertools.chain(
            (robot.serial for robot in entry.runtime_data.account.robots),
            (pet.id for pet in entry.runtime_data.account.pets),
        )
        if _id == identifier[1]
    )
