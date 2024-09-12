"""The iNELS integration."""

from __future__ import annotations

from typing import Any

from inelsmqtt import InelsMqtt
from inelsmqtt.discovery import InelsDiscovery

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import BROKER, BROKER_CONFIG, DEVICES, DOMAIN, LOGGER, OLD_ENTITIES

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
]


async def async_remove_old_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove old entities that aren't being used."""
    entity_registry = er.async_get(hass)
    remaining_entries = hass.data[DOMAIN][entry.entry_id][OLD_ENTITIES]

    for platform in remaining_entries:
        for entity_id in remaining_entries[platform]:
            entity_registry.async_remove(entity_id)


async def async_remove_devices_with_no_entities(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Remove devices with no entities."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    registered_devices = [
        entry.id
        for entry in dr.async_entries_for_config_entry(
            registry=device_registry, config_entry_id=entry.entry_id
        )
    ]

    for device_id in registered_devices:
        if not er.async_entries_for_device(
            entity_registry, device_id, include_disabled_entities=True
        ):
            LOGGER.info("Removing device %s, because it has no entities", device_id)
            device_registry.async_remove_device(device_id=device_id)


async def _async_config_entry_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Call when config entry being updated."""

    client: InelsMqtt = hass.data[BROKER]

    await hass.async_add_executor_job(client.disconnect)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up iNELS from a config entry."""

    inels_data: dict[str, Any] = {
        BROKER_CONFIG: entry.data,
    }

    mqtt = InelsMqtt(inels_data[BROKER_CONFIG])
    inels_data[BROKER] = mqtt

    conn_result = await hass.async_add_executor_job(inels_data[BROKER].test_connection)
    if isinstance(conn_result, int):  # None -> no error, int -> error code
        return False

    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = inels_data

    try:
        i_disc = InelsDiscovery(inels_data[BROKER])
        await hass.async_add_executor_job(i_disc.discovery)

        inels_data[DEVICES] = i_disc.devices
    except Exception as exc:
        await hass.async_add_executor_job(mqtt.close)
        raise ConfigEntryNotReady from exc

    LOGGER.debug("Finished discovery, setting up platforms")

    # save entity ids of old entities
    old_entries: dict[str, list[str]] = {}

    entity_registry = er.async_get(hass)
    registry_entries: list[er.RegistryEntry] = er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    )
    for entity in registry_entries:
        if entity.domain not in old_entries:
            old_entries[entity.domain] = []
        old_entries[entity.domain].append(entity.entity_id)

    inels_data[OLD_ENTITIES] = old_entries

    hass.data[DOMAIN][entry.entry_id] = inels_data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    LOGGER.info("Cleaning up entities/devices")
    await async_remove_old_entities(hass, entry)
    await async_remove_devices_with_no_entities(hass, entry)

    LOGGER.info("Platform setup complete")
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload all devices."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass_data = hass.data[DOMAIN][entry.entry_id]
    broker: InelsMqtt = hass_data[BROKER]

    broker.unsubscribe_listeners()
    broker.disconnect()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return True
