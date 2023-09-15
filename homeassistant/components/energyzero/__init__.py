"""The EnergyZero integration."""
from __future__ import annotations

from energyzero import EnergyZero

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SERVICE_NAME, SERVICE_PRICE_TYPES, SERVICE_SCHEMA
from .coordinator import EnergyZeroDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def _get_prices(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    """Search prices."""
    price_type = call.data["type"]

    if price_type not in SERVICE_PRICE_TYPES:
        raise ValueError(f"Invalid service type: {call.data['type']}")

    energyzero = EnergyZero(
        session=async_get_clientsession(hass),
        incl_btw="true" if call.data["incl_btw"] else "false",
    )

    start = dt_util.parse_datetime(call.data.get("start") or "") or dt_util.now().date()
    end = dt_util.parse_datetime(call.data.get("end") or "") or dt_util.now().date()

    response_data = {}

    if price_type == "energy" or price_type == "all":
        response_data["energy"] = (
            await energyzero.energy_prices(start_date=start, end_date=end)
        ).prices

    if price_type == "gas" or price_type == "all":
        response_data["gas"] = (
            await energyzero.gas_prices(start_date=start, end_date=end)
        ).prices

    return response_data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up EnergyZero from a config entry."""

    coordinator = EnergyZeroDataUpdateCoordinator(hass)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await coordinator.energyzero.close()
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def get_prices(call: ServiceCall) -> ServiceResponse:
        """Search prices."""
        return await _get_prices(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_NAME,
        get_prices,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload EnergyZero config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
