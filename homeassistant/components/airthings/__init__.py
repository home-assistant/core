"""The Airthings integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from airthings import Airthings, AirthingsDevice

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SECRET, DOMAIN
from .coordinator import AirthingsDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]
SCAN_INTERVAL = timedelta(minutes=6)

type AirthingsConfigEntry = ConfigEntry[AirthingsDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AirthingsConfigEntry) -> bool:
    """Set up Airthings from a config entry."""
    airthings = Airthings(
        entry.data[CONF_ID],
        entry.data[CONF_SECRET],
        async_get_clientsession(hass),
    )

    coordinator = AirthingsDataUpdateCoordinator(hass, airthings)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _remove_old_devices(hass, entry, coordinator.data)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirthingsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


def _remove_old_devices(
    hass: HomeAssistant,
    entry: AirthingsConfigEntry,
    airthings_devices: dict[str, AirthingsDevice],
) -> None:
    device_registry = dr.async_get(hass)

    for registered_device in device_registry.devices.get_devices_for_config_entry_id(
        entry.entry_id
    ):
        device_id = next(
            (i[1] for i in registered_device.identifiers if i[0] == DOMAIN), None
        )
        if device_id and device_id not in airthings_devices:
            _LOGGER.info(
                "Removing device %s with ID %s because it is no longer exists in your account",
                registered_device.name,
                device_id,
            )
            device_registry.async_update_device(
                registered_device.id, remove_config_entry_id=entry.entry_id
            )
