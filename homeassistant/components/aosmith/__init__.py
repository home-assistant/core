"""The A. O. Smith integration."""

from __future__ import annotations

from dataclasses import dataclass

from py_aosmith import AOSmithAPIClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, device_registry as dr

from .const import DOMAIN
from .coordinator import AOSmithEnergyCoordinator, AOSmithStatusCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.WATER_HEATER]


@dataclass
class AOSmithData:
    """Data for the A. O. Smith integration."""

    client: AOSmithAPIClient
    status_coordinator: AOSmithStatusCoordinator
    energy_coordinator: AOSmithEnergyCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up A. O. Smith from a config entry."""
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]

    session = aiohttp_client.async_get_clientsession(hass)
    client = AOSmithAPIClient(email, password, session)

    status_coordinator = AOSmithStatusCoordinator(hass, client)
    await status_coordinator.async_config_entry_first_refresh()

    device_registry = dr.async_get(hass)
    for junction_id, aosmith_device in status_coordinator.data.items():
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, junction_id)},
            manufacturer="A. O. Smith",
            name=aosmith_device.name,
            model=aosmith_device.model,
            serial_number=aosmith_device.serial,
            suggested_area=aosmith_device.install_location,
            sw_version=aosmith_device.status.firmware_version,
        )

    energy_coordinator = AOSmithEnergyCoordinator(
        hass, client, list(status_coordinator.data)
    )
    await energy_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = AOSmithData(
        client,
        status_coordinator,
        energy_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
