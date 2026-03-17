"""The Photoptimizer integration."""

from __future__ import annotations

import logging

from forecast_solar import ForecastSolar, ForecastSolarError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from .const import DOMAIN
from .coordinator import PhotoptimizerCoordinator

_LOGGER = logging.getLogger(__name__)
_PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.SELECT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Photoptimizer from a config entry.

    Create Forecast.Solar client, coordinator and store it so platforms can use it.
    """
    session = async_get_clientsession(hass)

    latitude = entry.data.get("latitude") or hass.config.latitude
    longitude = entry.data.get("longitude") or hass.config.longitude
    declination = entry.data.get("tilt") or entry.data.get("declination") or 0.0
    azimuth = entry.data.get("azimuth") or 0.0
    kwp = entry.data.get("kwp") or 0.0
    api_key = entry.data.get("api_key")

    if latitude is None or longitude is None:
        raise ConfigEntryNotReady("Latitude and longitude are required")

    client = ForecastSolar(
        session=session,
        latitude=float(latitude),
        longitude=float(longitude),
        declination=float(declination),
        azimuth=float(azimuth),
        kwp=float(kwp),
        damping=0,
        api_key=api_key,
    )

    try:
        await client.estimate()
    except ForecastSolarError as err:
        _LOGGER.debug("ForecastSolar validation failed: %s", err)
        raise ConfigEntryNotReady(
            f"Unable to connect to Forecast.Solar: {err}"
        ) from err
    except Exception as err:
        _LOGGER.debug("Unexpected error during Forecast.Solar validation: %s", err)
        raise ConfigEntryNotReady(
            f"Unexpected error connecting to Forecast.Solar: {err}"
        ) from err

    coordinator = PhotoptimizerCoordinator(hass, entry, client)

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as err:
        if isinstance(err.__cause__, UpdateFailed) and str(err.__cause__) == (
            "EMHASS optimization failed"
        ):
            _LOGGER.warning(
                "Initial EMHASS refresh failed; loading integration with unavailable entities"
            )
        else:
            raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        entry.runtime_data = None
    return unload_ok
