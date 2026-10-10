"""The Rituals Perfume Genie integration."""

import asyncio

from ritualsgenie import (
    RitualsGenie,
    RitualsGenieAuthenticationError,
    RitualsGenieError,
    RitualsGenieHub,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ACCOUNT_HASH, UPDATE_INTERVAL
from .coordinator import RitualsConfigEntry, RitualsDataUpdateCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: RitualsConfigEntry) -> bool:
    """Set up Rituals Perfume Genie from a config entry."""
    # Initiate reauth for old config entries which don't have
    # username / password in the entry data
    if CONF_EMAIL not in entry.data or CONF_PASSWORD not in entry.data:
        raise ConfigEntryAuthFailed("Missing credentials")

    client = RitualsGenie(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
    )

    try:
        hubs = await client.hubs()
    except RitualsGenieAuthenticationError as err:
        raise ConfigEntryAuthFailed(err) from err
    except RitualsGenieError as err:
        raise ConfigEntryNotReady(err) from err

    # Migrate old unique_ids to the new format
    async_migrate_entities_unique_ids(hass, entry, hubs)

    # The API provided by Rituals is currently rate limited to 30 requests
    # per hour per IP address. To avoid hitting this limit, we will adjust
    # the polling interval based on the number of diffusers one has.
    update_interval = UPDATE_INTERVAL * len(hubs)

    # Create a coordinator for each diffuser
    coordinators = {
        hub.hublot: RitualsDataUpdateCoordinator(
            hass, entry, client, hub, update_interval
        )
        for hub in hubs
    }

    # Refresh all coordinators
    await asyncio.gather(
        *[
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators.values()
        ]
    )

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RitualsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@callback
def async_migrate_entities_unique_ids(
    hass: HomeAssistant, config_entry: ConfigEntry, hubs: list[RitualsGenieHub]
) -> None:
    """Migrate unique_ids in the entity registry to the new format."""
    entity_registry = er.async_get(hass)
    registry_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )

    conversion: dict[tuple[str, str], str] = {
        (Platform.BINARY_SENSOR, " Battery Charging"): "charging",
        (Platform.NUMBER, " Perfume Amount"): "perfume_amount",
        (Platform.SELECT, " Room Size"): "room_size_square_meter",
        (Platform.SENSOR, " Battery"): "battery_percentage",
        (Platform.SENSOR, " Fill"): "fill",
        (Platform.SENSOR, " Perfume"): "perfume",
        (Platform.SENSOR, " Wifi"): "wifi_percentage",
        (Platform.SWITCH, ""): "is_on",
    }

    for hub in hubs:
        for registry_entry in registry_entries:
            if new_unique_id := conversion.get(
                (
                    registry_entry.domain,
                    registry_entry.unique_id.removeprefix(hub.hublot),
                )
            ):
                entity_registry.async_update_entity(
                    registry_entry.entity_id,
                    new_unique_id=f"{hub.hublot}-{new_unique_id}",
                )


# Migration helpers for API v2
async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry to version 2: drop legacy ACCOUNT_HASH and bump version."""
    if entry.version < 2:
        data = dict(entry.data)
        data.pop(ACCOUNT_HASH, None)
        hass.config_entries.async_update_entry(entry, data=data, version=2)
        return True
    return True
