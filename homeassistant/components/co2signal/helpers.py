"""Helper functions for the CO2 Signal integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aioelectricitymaps import ElectricityMaps
from aioelectricitymaps.models import CarbonIntensityResponse

from homeassistant.const import CONF_COUNTRY_CODE, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant


async def fetch_latest_carbon_intensity(
    hass: HomeAssistant,
    em: ElectricityMaps,
    config: Mapping[str, Any],
) -> CarbonIntensityResponse:
    """Fetch the latest carbon intensity based on country code or location coordinates."""
    if CONF_COUNTRY_CODE in config:
        return await em.latest_carbon_intensity_by_country_code(
            code=config[CONF_COUNTRY_CODE]
        )

    return await em.latest_carbon_intensity_by_coordinates(
        lat=config.get(CONF_LATITUDE, hass.config.latitude),
        lon=config.get(CONF_LONGITUDE, hass.config.longitude),
    )
