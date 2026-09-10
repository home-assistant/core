"""Integration for Apple's WeatherKit API."""

from apple_weatherkit.client import (
    WeatherKitApiClient,
    WeatherKitApiClientAuthenticationError,
    WeatherKitApiClientError,
)

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_KEY_ID,
    CONF_KEY_PEM,
    CONF_SERVICE_ID,
    CONF_TEAM_ID,
    DOMAIN,
    LOGGER,
)
from .coordinator import WeatherKitConfigEntry, WeatherKitDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: WeatherKitConfigEntry) -> bool:
    """Set up this integration using UI."""
    coordinator = WeatherKitDataUpdateCoordinator(
        hass=hass,
        config_entry=entry,
        client=WeatherKitApiClient(
            key_id=entry.data[CONF_KEY_ID],
            service_id=entry.data[CONF_SERVICE_ID],
            team_id=entry.data[CONF_TEAM_ID],
            key_pem=entry.data[CONF_KEY_PEM],
            session=async_get_clientsession(hass),
        ),
    )

    try:
        await coordinator.update_supported_data_sets()
    except WeatherKitApiClientAuthenticationError as ex:
        LOGGER.error("Authentication error initializing integration: %s", ex)
        return False
    except WeatherKitApiClientError as ex:
        raise ConfigEntryNotReady from ex

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WeatherKitConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, entry: WeatherKitConfigEntry
) -> bool:
    """Migrate old entry."""
    if entry.version == 1:
        # Move entity/device identity off the (mutable) location and onto the
        # entry_id so that reconfiguring the location doesn't orphan them.
        old_unique_id = f"{entry.data[CONF_LATITUDE]}-{entry.data[CONF_LONGITUDE]}"

        device_registry = dr.async_get(hass)
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, old_unique_id), entry.entry_id
        )
        if device is not None:
            device_registry.async_update_device(
                device.id, new_identifiers={(DOMAIN, entry.entry_id)}
            )

        entity_registry = er.async_get(hass)
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if entity_entry.unique_id == old_unique_id:
                new_unique_id = entry.entry_id
            elif entity_entry.unique_id.startswith(f"{old_unique_id}_"):
                suffix = entity_entry.unique_id.removeprefix(old_unique_id)
                new_unique_id = f"{entry.entry_id}{suffix}"
            else:
                continue

            entity_registry.async_update_entity(
                entity_entry.entity_id, new_unique_id=new_unique_id
            )

        hass.config_entries.async_update_entry(entry, version=2)

    return True
