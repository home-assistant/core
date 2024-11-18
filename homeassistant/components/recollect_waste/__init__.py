"""The ReCollect Waste integration."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from aiorecollect.client import Client, PickupEvent
from aiorecollect.errors import RecollectError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client, entity_registry as er
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_PLACE_ID, CONF_SERVICE_ID, DOMAIN, LOGGER

DEFAULT_NAME = "recollect_waste"
DEFAULT_UPDATE_INTERVAL = timedelta(days=1)

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RainMachine as config entry."""
    session = aiohttp_client.async_get_clientsession(hass)
    client = Client(
        entry.data[CONF_PLACE_ID], entry.data[CONF_SERVICE_ID], session=session
    )

    async def async_get_pickup_events() -> list[PickupEvent]:
        """Get the next pickup."""
        try:
            # Retrieve today through to 35 days in the future, to get
            # coverage across a full two months boundary so that no
            # upcoming pickups are missed. The api.recollect.net base API
            # call returns only the current month when no dates are passed.
            # This ensures that data about when the next pickup is will be
            # returned when the next pickup is the first day of the next month.
            # Ex: Today is August 31st, tomorrow is a pickup on September 1st.
            today = date.today()
            return await client.async_get_pickup_events(
                start_date=today,
                end_date=today + timedelta(days=35),
            )
        except RecollectError as err:
            raise UpdateFailed(
                f"Error while requesting data from ReCollect: {err}"
            ) from err

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        config_entry=entry,
        name=(
            f"Place {entry.data[CONF_PLACE_ID]}, Service {entry.data[CONF_SERVICE_ID]}"
        ),
        update_interval=DEFAULT_UPDATE_INTERVAL,
        update_method=async_get_pickup_events,
    )

    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an RainMachine config entry."""
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
        version = 2
        hass.config_entries.async_update_entry(entry, version=version)

        @callback
        def migrate_unique_id(entity_entry: er.RegistryEntry) -> dict[str, Any]:
            """Migrate the unique ID to a new format."""
            return {
                "new_unique_id": (
                    f"{entry.data[CONF_PLACE_ID]}_"
                    f"{entry.data[CONF_SERVICE_ID]}_"
                    "current_pickup"
                )
            }

        await er.async_migrate_entries(hass, entry.entry_id, migrate_unique_id)

    LOGGER.debug("Migration to version %s successful", version)

    return True
