"""The Airly integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.components.air_quality import DOMAIN as AIR_QUALITY_PLATFORM
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_USE_NEAREST, DOMAIN, MIN_UPDATE_INTERVAL
from .coordinator import AirlyDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

type AirlyConfigEntry = ConfigEntry[AirlyDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AirlyConfigEntry) -> bool:
    """Set up Airly as config entry."""
    api_key = entry.data[CONF_API_KEY]
    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    use_nearest = entry.data.get(CONF_USE_NEAREST, False)

    # For backwards compat, set unique ID
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=f"{latitude}-{longitude}"
        )

    # identifiers in device_info should use tuple[str, str] type, but latitude and
    # longitude are float, so we convert old device entries to use correct types
    # We used to use a str 3-tuple here sometime, convert that to a 2-tuple too.
    device_registry = dr.async_get(hass)
    old_ids = (DOMAIN, latitude, longitude)
    for old_ids in (
        (DOMAIN, latitude, longitude),
        (
            DOMAIN,
            str(latitude),
            str(longitude),
        ),
    ):
        device_entry = device_registry.async_get_device(identifiers={old_ids})  # type: ignore[arg-type]
        if device_entry and entry.entry_id in device_entry.config_entries:
            new_ids = (DOMAIN, f"{latitude}-{longitude}")
            device_registry.async_update_device(
                device_entry.id, new_identifiers={new_ids}
            )

    websession = async_get_clientsession(hass)

    update_interval = timedelta(minutes=MIN_UPDATE_INTERVAL)

    coordinator = AirlyDataUpdateCoordinator(
        hass, websession, api_key, latitude, longitude, update_interval, use_nearest
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Remove air_quality entities from registry if they exist
    ent_reg = er.async_get(hass)
    unique_id = f"{coordinator.latitude}-{coordinator.longitude}"
    if entity_id := ent_reg.async_get_entity_id(
        AIR_QUALITY_PLATFORM, DOMAIN, unique_id
    ):
        _LOGGER.debug("Removing deprecated air_quality entity %s", entity_id)
        ent_reg.async_remove(entity_id)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirlyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
