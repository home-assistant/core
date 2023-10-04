"""The Renson Healthbox integration."""
from __future__ import annotations

from pyhealthbox3.healthbox3 import Healthbox3

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ALL_SERVICES,
    DOMAIN,
    PLATFORMS,
    SERVICE_START_ROOM_BOOST,
    SERVICE_START_ROOM_BOOST_SCHEMA,
    SERVICE_STOP_ROOM_BOOST,
    SERVICE_STOP_ROOM_BOOST_SCHEMA,
)
from .coordinator import HealthboxDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Renson Healthbox from a config entry."""
    api_key = None

    if CONF_API_KEY in entry.data:
        api_key = entry.data[CONF_API_KEY]

    api: Healthbox3 = Healthbox3(
        host=entry.data[CONF_HOST],
        api_key=api_key,
        session=async_get_clientsession(hass),
    )
    if api_key:
        await api.async_enable_advanced_api_features()

    coordinator = HealthboxDataUpdateCoordinator(hass=hass, entry=entry, api=api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Define Services
    async def start_room_boost(call: ServiceCall) -> None:
        """Service call to start boosting fans in a room."""
        device_id = call.data["device_id"]
        device_registry = dr.async_get(hass)
        device = device_registry.async_get(device_id)

        if device:
            device_identifier = next(iter(device.identifiers))[1]
            room_id: int = int(device_identifier.split("_")[-1])
            await coordinator.start_room_boost(
                room_id=room_id,
                boost_level=call.data["boost_level"],
                boost_timeout=call.data["boost_timeout"] * 60,
            )

    async def stop_room_boost(call: ServiceCall) -> None:
        """Service call to stop boosting fans in a room."""
        device_id = call.data["device_id"]
        device_registry = dr.async_get(hass)
        device = device_registry.async_get(device_id)

        if device:
            device_identifier = next(iter(device.identifiers))[1]
            room_id: int = int(device_identifier.split("_")[-1])
            await coordinator.stop_room_boost(room_id=room_id)

    # Register Services
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_ROOM_BOOST,
        start_room_boost,
        SERVICE_START_ROOM_BOOST_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_STOP_ROOM_BOOST, stop_room_boost, SERVICE_STOP_ROOM_BOOST_SCHEMA
    )

    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            del hass.data[DOMAIN]

        for service in ALL_SERVICES:
            hass.services.async_remove(DOMAIN, service)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry):
    """Reload entry if options change."""
    await hass.config_entries.async_reload(entry.entry_id)
