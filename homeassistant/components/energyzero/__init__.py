"""The EnergyZero integration."""
from __future__ import annotations

from datetime import date, datetime
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

from .const import DOMAIN, SERVICE_NAME, SERVICE_SCHEMA
from .coordinator import EnergyZeroDataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]

def _get_date(date_input: str) -> date | datetime:
    """Get date."""
    if not date_input:
        return dt_util.now().date()

    if value := dt_util.parse_datetime(date_input):
        return value
    else:
        raise ValueError(f"Invalid date: {date_input}")

async def _get_prices(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    """Search prices."""
    price_type = call.data["type"]

    energyzero = EnergyZero(
        session=async_get_clientsession(hass),
        incl_btw=str(call.data["incl_btw"]).lower(),
    )

    start = _get_date(call.data.get("start", ""))
    end = _get_date(call.data.get("end", ""))

    if price_type == "energy":
        return (
            await energyzero.energy_prices(start_date=start, end_date=end)
        ).prices

    elif price_type == "gas":
        return (
            await energyzero.gas_prices(start_date=start, end_date=end)
        ).prices

    return {}


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
