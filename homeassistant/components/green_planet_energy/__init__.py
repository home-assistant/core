"""Green Planet Energy integration for Home Assistant."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import GreenPlanetEnergyUpdateCoordinator
from .sensor import get_current_price

PLATFORMS: list[Platform] = [Platform.SENSOR]

# Config entry only (no YAML config)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# Service schema
SERVICE_GET_PRICE_SCHEMA = vol.Schema(
    {
        vol.Optional("hour"): vol.All(vol.Coerce(int), vol.Range(min=0, max=23)),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Green Planet Energy component."""

    async def async_get_price(call: ServiceCall) -> ServiceResponse:
        """Get price for a specific hour or current price."""
        hour = call.data.get("hour")

        # Find the first configured entry (should only be one due to single instance)
        config_entries = hass.config_entries.async_entries(DOMAIN)
        if not config_entries:
            raise ServiceValidationError(
                "No Green Planet Energy integration configured"
            )

        entry = config_entries[0]
        if not entry.runtime_data:
            raise ServiceValidationError("Green Planet Energy integration not ready")

        coordinator = entry.runtime_data

        if hour is not None:
            # Get price for specific hour
            price_key = f"gpe_price_{hour:02d}"
            price = coordinator.data.get(price_key)
            if price is None:
                raise ServiceValidationError(f"No price data available for hour {hour}")

            return {
                "hour": hour,
                "price": price,
                "time_slot": f"{hour:02d}:00-{hour + 1:02d}:00",
                "unit": "€/kWh",
            }

        # Get current price
        current_price = get_current_price(coordinator.data)
        if current_price is None:
            raise ServiceValidationError("No current price data available")

        current_hour = dt_util.now().hour

        return {
            "hour": current_hour,
            "price": current_price,
            "time_slot": f"{current_hour:02d}:00-{current_hour + 1:02d}:00",
            "unit": "€/kWh",
        }

    hass.services.async_register(
        DOMAIN,
        "get_price",
        async_get_price,
        schema=SERVICE_GET_PRICE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Green Planet Energy from a config entry."""
    coordinator = GreenPlanetEnergyUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
