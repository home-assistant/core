"""The Airgradient integration."""

from __future__ import annotations

from airgradient import AirGradientClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import AirGradientConfigCoordinator, AirGradientMeasurementCoordinator

PLATFORMS: list[Platform] = [Platform.SELECT, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Airgradient from a config entry."""

    client = AirGradientClient(
        entry.data[CONF_HOST], session=async_get_clientsession(hass)
    )

    measurement_coordinator = AirGradientMeasurementCoordinator(hass, client)
    config_coordinator = AirGradientConfigCoordinator(hass, client)

    await measurement_coordinator.async_config_entry_first_refresh()
    await config_coordinator.async_config_entry_first_refresh()

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, measurement_coordinator.serial_number)},
        manufacturer="AirGradient",
        model=measurement_coordinator.data.model,
        serial_number=measurement_coordinator.data.serial_number,
        sw_version=measurement_coordinator.data.firmware_version,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "measurement": measurement_coordinator,
        "config": config_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
