"""The Ridwell integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from aioridwell import async_get_client
from aioridwell.errors import InvalidCredentialsError, RidwellError
from aioridwell.model import RidwellAccount, RidwellPickupEvent

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, entity_registry as er
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DATA_ACCOUNT,
    DATA_COORDINATOR,
    DOMAIN,
    LOGGER,
    SENSOR_TYPE_NEXT_PICKUP,
)

DEFAULT_UPDATE_INTERVAL = timedelta(hours=1)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ridwell from a config entry."""
    session = aiohttp_client.async_get_clientsession(hass)

    try:
        client = await async_get_client(
            entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session=session
        )
    except InvalidCredentialsError as err:
        raise ConfigEntryAuthFailed("Invalid username/password") from err
    except RidwellError as err:
        raise ConfigEntryNotReady(err) from err

    accounts = await client.async_get_accounts()

    async def async_update_data() -> dict[str, RidwellPickupEvent]:
        """Get the latest pickup events."""
        data = {}

        async def async_get_pickups(account: RidwellAccount) -> None:
            """Get the latest pickups for an account."""
            data[account.account_id] = await account.async_get_next_pickup_event()

        tasks = [async_get_pickups(account) for account in accounts.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, InvalidCredentialsError):
                raise ConfigEntryAuthFailed("Invalid username/password") from result
            if isinstance(result, RidwellError):
                raise UpdateFailed(result) from result

        return data

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=entry.title,
        update_interval=DEFAULT_UPDATE_INTERVAL,
        update_method=async_update_data,
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_ACCOUNT: accounts,
        DATA_COORDINATOR: coordinator,
    }

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""
    version = entry.version

    LOGGER.debug("Migrating from version %s", version)

    # 1 -> 2: Update unique ID of existing, single sensor entity to be consistent with
    # common format for platforms going forward:
    if version == 1:
        version = entry.version = 2

        @callback
        def migrate_unique_id(entity_entry: er.RegistryEntry) -> dict[str, Any]:
            """Migrate the unique ID to a new format."""
            return {
                "new_unique_id": f"{entity_entry.unique_id}_{SENSOR_TYPE_NEXT_PICKUP}"
            }

        await er.async_migrate_entries(hass, entry.entry_id, migrate_unique_id)

    LOGGER.info("Migration to version %s successful", version)

    return True


class RidwellEntity(CoordinatorEntity):
    """Define a base Ridwell entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        account: RidwellAccount,
        description: EntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)

        self._account = account
        self._attr_unique_id = f"{account.account_id}_{description.key}"
        self.entity_description = description
