"""The iNELS integration."""

from __future__ import annotations

from dataclasses import dataclass, field

from inelsmqtt import InelsMqtt
from inelsmqtt.devices import Device
from inelsmqtt.discovery import InelsDiscovery

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import LOGGER

type InelsConfigEntry = ConfigEntry[InelsData]

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
]


@dataclass
class InelsData:
    """Represents the data structure for INELS runtime data."""

    mqtt: InelsMqtt
    devices: list[Device] = field(default_factory=list)
    old_entities: dict[Platform, list[str]] = field(default_factory=dict)


async def async_remove_old_entities(
    hass: HomeAssistant, entry: InelsConfigEntry
) -> None:
    """Remove old entities that aren't being used."""
    entity_registry = er.async_get(hass)
    remaining_entries = entry.runtime_data.old_entities

    for platform in remaining_entries:
        for entity_id in remaining_entries[platform]:
            entity_registry.async_remove(entity_id)

        # Clear the list for the platform after removing entities
        remaining_entries[platform].clear()


async def async_remove_devices_with_no_entities(
    hass: HomeAssistant, entry: InelsConfigEntry
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


async def _async_config_entry_updated(
    hass: HomeAssistant, entry: InelsConfigEntry
) -> None:
    """Call when config entry being updated."""

    await hass.async_add_executor_job(entry.runtime_data.mqtt.disconnect)


async def async_setup_entry(hass: HomeAssistant, entry: InelsConfigEntry) -> bool:
    """Set up iNELS from a config entry."""

    mqtt = InelsMqtt(entry.data)
    inels_data = InelsData(mqtt=mqtt)

    # Test connection and check for authentication errors
    conn_result = await hass.async_add_executor_job(mqtt.test_connection)
    if isinstance(conn_result, int):  # None -> no error, int -> error code
        await hass.async_add_executor_job(mqtt.close)
        if conn_result in (4, 5):
            raise ConfigEntryAuthFailed("Invalid authentication")
        if conn_result == 3:
            raise ConfigEntryNotReady("MQTT Broker is offline or cannot be reached")
        return False

    entry.runtime_data = inels_data

    try:
        i_disc = InelsDiscovery(mqtt)
        await hass.async_add_executor_job(i_disc.discovery)

        inels_data.devices = i_disc.devices
    except Exception as exc:
        await hass.async_add_executor_job(mqtt.close)
        raise ConfigEntryNotReady from exc

    LOGGER.debug("Finished discovery, setting up platforms")

    entity_registry = er.async_get(hass)
    registry_entries: list[er.RegistryEntry] = er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    )
    for entity in registry_entries:
        platform = Platform(entity.domain)
        if platform not in inels_data.old_entities:
            inels_data.old_entities[platform] = []
        inels_data.old_entities[platform].append(entity.entity_id)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    LOGGER.info("Cleaning up entities/devices")
    await async_remove_old_entities(hass, entry)
    await async_remove_devices_with_no_entities(hass, entry)

    LOGGER.info("Platform setup complete")
    return True


async def async_reload_entry(hass: HomeAssistant, entry: InelsConfigEntry) -> None:
    """Reload all devices."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: InelsConfigEntry) -> bool:
    """Unload a config entry."""
    entry.runtime_data.mqtt.unsubscribe_listeners()
    entry.runtime_data.mqtt.disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
