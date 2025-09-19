"""Helper functions for the CO2 Signal integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aioelectricitymaps import (
    CoordinatesRequest,
    ElectricityMaps,
    HomeAssistantCarbonIntensityResponse,
    ZoneRequest,
)

from homeassistant.const import CONF_COUNTRY_CODE, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant


async def fetch_latest_carbon_intensity(
    hass: HomeAssistant,
    em: ElectricityMaps,
    config: Mapping[str, Any],
) -> HomeAssistantCarbonIntensityResponse:
    """Fetch the latest carbon intensity based on country code or location coordinates."""
    request: CoordinatesRequest | ZoneRequest = CoordinatesRequest(
        lat=config.get(CONF_LATITUDE, hass.config.latitude),
        lon=config.get(CONF_LONGITUDE, hass.config.longitude),
    )

    if CONF_COUNTRY_CODE in config:
        request = ZoneRequest(
            zone=config[CONF_COUNTRY_CODE],
        )

    return await em.carbon_intensity_for_home_assistant(request)
