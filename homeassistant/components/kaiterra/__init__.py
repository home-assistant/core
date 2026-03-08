"""The Kaiterra integration."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, CONF_DEVICE_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api_data import KaiterraApiClient
from .const import CONF_AQI_STANDARD, DEFAULT_AQI_STANDARD, DOMAIN, LOGGER, PLATFORMS
from .coordinator import KaiterraConfigEntry, KaiterraDataUpdateCoordinator

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

LEGACY_SENSOR_UNIQUE_ID_MIGRATIONS: dict[str, str] = {
    "temperature": "rtemp",
    "humidity": "rhumid",
}


def _async_remove_legacy_air_quality_entity(
    hass: HomeAssistant, entry: KaiterraConfigEntry
) -> None:
    """Remove the legacy air quality entity registry entry."""
    entity_registry = er.async_get(hass)
    old_unique_id = f"{entry.unique_id}_air_quality"

    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if entity_entry.unique_id == old_unique_id:
            entity_registry.async_remove(entity_entry.entity_id)


def _async_migrate_legacy_sensor_unique_ids(
    hass: HomeAssistant, entry: KaiterraConfigEntry
) -> None:
    """Migrate legacy sensor unique IDs to the config entry format."""
    entity_registry = er.async_get(hass)

    for legacy_suffix, current_suffix in LEGACY_SENSOR_UNIQUE_ID_MIGRATIONS.items():
        old_unique_id = f"{entry.unique_id}_{legacy_suffix}"
        new_unique_id = f"{entry.unique_id}_{current_suffix}"

        if not (
            old_entity_id := entity_registry.async_get_entity_id(
                "sensor", DOMAIN, old_unique_id
            )
        ):
            continue

        if duplicate_entity_id := entity_registry.async_get_entity_id(
            "sensor", DOMAIN, new_unique_id
        ):
            entity_registry.async_remove(duplicate_entity_id)

        entity_registry.async_update_entity(
            old_entity_id,
            config_entry_id=entry.entry_id,
            new_unique_id=new_unique_id,
        )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Kaiterra from configuration.yaml."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: KaiterraConfigEntry) -> bool:
    """Set up Kaiterra from a config entry."""
    _async_remove_legacy_air_quality_entity(hass, entry)

    coordinator = KaiterraDataUpdateCoordinator(
        hass,
        entry,
        KaiterraApiClient(
            async_get_clientsession(hass),
            entry.data[CONF_API_KEY],
            entry.options.get(CONF_AQI_STANDARD, DEFAULT_AQI_STANDARD),
        ),
        entry.data[CONF_DEVICE_ID],
        entry.data.get(CONF_NAME) or entry.title,
    )

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: KaiterraConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: KaiterraConfigEntry) -> bool:
    """Migrate old config entries."""
    if entry.version > 1:
        return False

    version = entry.version
    minor_version = entry.minor_version

    if version == 1 and minor_version < 2:
        _async_remove_legacy_air_quality_entity(hass, entry)
        minor_version = 2

    if version == 1 and minor_version < 3:
        _async_migrate_legacy_sensor_unique_ids(hass, entry)
        minor_version = 3

    if minor_version != entry.minor_version:
        hass.config_entries.async_update_entry(entry, minor_version=minor_version)
        LOGGER.debug("Migration to version %s.%s successful", version, minor_version)

    return True
