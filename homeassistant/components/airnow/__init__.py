"""The AirNow integration."""

import datetime
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN  # noqa: F401
from .coordinator import AirNowDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]

type AirNowConfigEntry = ConfigEntry[AirNowDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AirNowConfigEntry) -> bool:
    """Set up AirNow from a config entry."""
    api_key = entry.data[CONF_API_KEY]
    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]

    # Station Radius is a user-configurable option
    distance = entry.options[CONF_RADIUS]

    # Reports are published hourly but update twice per hour
    update_interval = datetime.timedelta(minutes=30)

    # Setup the Coordinator
    session = async_get_clientsession(hass)
    coordinator = AirNowDataUpdateCoordinator(
        hass, session, api_key, latitude, longitude, distance, update_interval
    )

    # Sync with Coordinator
    await coordinator.async_config_entry_first_refresh()

    # Store Entity and Initialize Platforms
    entry.runtime_data = coordinator

    # Listen for option changes
    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Clean up unused device entries with no entities
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    device_entries = dr.async_entries_for_config_entry(
        device_registry, config_entry_id=entry.entry_id
    )
    for dev in device_entries:
        dev_entities = er.async_entries_for_device(
            entity_registry, dev.id, include_disabled_entities=True
        )
        if not dev_entities:
            device_registry.async_remove_device(dev.id)

    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        new_options = {CONF_RADIUS: entry.data[CONF_RADIUS]}
        new_data = entry.data.copy()
        del new_data[CONF_RADIUS]

        hass.config_entries.async_update_entry(
            entry, data=new_data, options=new_options, version=2
        )

    _LOGGER.info("Migration to version %s successful", entry.version)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirNowConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
