"""The Rituals Perfume Genie integration."""

import asyncio

import aiohttp
from pyrituals import Account, Diffuser

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ACCOUNT_HASH, DOMAIN, UPDATE_INTERVAL
from .coordinator import RitualsDataUpdateCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rituals Perfume Genie from a config entry."""
    session = async_get_clientsession(hass)
    account = Account(session=session, account_hash=entry.data[ACCOUNT_HASH])

    try:
        account_devices = await account.get_devices()
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    # Migrate old unique_ids to the new format
    async_migrate_entities_unique_ids(hass, entry, account_devices)

    # The API provided by Rituals is currently rate limited to 30 requests
    # per hour per IP address. To avoid hitting this limit, we will adjust
    # the polling interval based on the number of diffusers one has.
    update_interval = UPDATE_INTERVAL * len(account_devices)

    # Create a coordinator for each diffuser
    coordinators = {
        diffuser.hublot: RitualsDataUpdateCoordinator(
            hass, entry, diffuser, update_interval
        )
        for diffuser in account_devices
    }

    # Refresh all coordinators
    await asyncio.gather(
        *[
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators.values()
        ]
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


@callback
def async_migrate_entities_unique_ids(
    hass: HomeAssistant, config_entry: ConfigEntry, diffusers: list[Diffuser]
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

    for diffuser in diffusers:
        for registry_entry in registry_entries:
            if new_unique_id := conversion.get(
                (
                    registry_entry.domain,
                    registry_entry.unique_id.removeprefix(diffuser.hublot),
                )
            ):
                entity_registry.async_update_entity(
                    registry_entry.entity_id,
                    new_unique_id=f"{diffuser.hublot}-{new_unique_id}",
                )
