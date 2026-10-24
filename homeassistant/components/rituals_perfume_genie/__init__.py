"""The Rituals Perfume Genie integration."""

import asyncio

from ritualsgenie import RitualsGenie, RitualsGenieHub

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ACCOUNT_HASH, DOMAIN
from .coordinator import (
    RitualsConfigEntry,
    RitualsHubsCoordinator,
    RitualsRuntimeData,
    RitualsSensorsCoordinator,
)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
]


async def async_setup_entry(hass: HomeAssistant, entry: RitualsConfigEntry) -> None:
    """Set up Rituals Perfume Genie from a config entry."""
    # Initiate reauth for old config entries which don't have
    # username / password in the entry data
    if CONF_EMAIL not in entry.data or CONF_PASSWORD not in entry.data:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="missing_credentials"
        )

    client = RitualsGenie(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        session=async_get_clientsession(hass),
        token=entry.data.get(CONF_TOKEN),
    )

    hubs = RitualsHubsCoordinator(hass, entry, client)
    await hubs.async_config_entry_first_refresh()

    # Migrate old unique_ids to the new format
    async_migrate_entities_unique_ids(hass, entry, list(hubs.data.values()))

    sensors = {
        hublot: RitualsSensorsCoordinator(hass, entry, hubs, hublot)
        for hublot in hubs.data
    }

    entry.runtime_data = RitualsRuntimeData(hubs=hubs, sensors=sensors)
    async_update_diffusers(hass, entry)

    # Before the platforms: they look for the sensors coordinator of a new
    # diffuser when the same update tells them about it.
    entry.async_on_unload(
        hubs.async_add_listener(lambda: async_update_diffusers(hass, entry))
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Only now the entities are listening, so the coordinators know which
    # sensors to fetch. Not a first refresh on purpose: when the sensors fail,
    # the diffusers can still be controlled. Rituals has blocked just the
    # sensors before.
    await asyncio.gather(
        *(coordinator.async_refresh() for coordinator in sensors.values())
    )


@callback
def async_update_diffusers(hass: HomeAssistant, entry: RitualsConfigEntry) -> None:
    """Follow the diffusers being added to and removed from the account.

    A new diffuser gets a sensors coordinator. A removed one loses its
    device, and with that its entities.
    """
    runtime_data = entry.runtime_data
    hubs = runtime_data.hubs.data

    for hublot in hubs.keys() - runtime_data.sensors.keys():
        runtime_data.sensors[hublot] = RitualsSensorsCoordinator(
            hass, entry, runtime_data.hubs, hublot, added=True
        )

    for hublot in runtime_data.sensors.keys() - hubs.keys():
        del runtime_data.sensors[hublot]

    device_registry = dr.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        if not any(
            domain == DOMAIN and hublot in hubs for domain, hublot in device.identifiers
        ):
            device_registry.async_remove_device(device.id)


async def async_unload_entry(hass: HomeAssistant, entry: RitualsConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


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
async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate config entry to version 2: drop legacy ACCOUNT_HASH and bump version."""
    if entry.version < 2:
        data = dict(entry.data)
        data.pop(ACCOUNT_HASH, None)
        hass.config_entries.async_update_entry(entry, data=data, version=2)
        return
