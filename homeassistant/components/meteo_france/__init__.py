"""Support for Meteo-France weather data."""

import logging

from meteofrance_api.client import MeteoFranceClient
from meteofrance_api.helpers import is_valid_warning_department

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import METEO_FRANCE_DATA, PLATFORMS
from .coordinator import (
    MeteoFranceAlertUpdateCoordinator,
    MeteoFranceConfigEntry,
    MeteoFranceData,
    MeteoFranceForecastUpdateCoordinator,
    MeteoFranceRainUpdateCoordinator,
    RainForecastNotAvailable,
)

_LOGGER = logging.getLogger(__name__)


async def _async_get_rain_coordinator(
    hass: HomeAssistant, entry: MeteoFranceConfigEntry, client: MeteoFranceClient
) -> MeteoFranceRainUpdateCoordinator | None:
    """Return the rain coordinator, None if the place has no rain forecast."""
    coordinator = MeteoFranceRainUpdateCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        if not isinstance(coordinator.last_exception, RainForecastNotAvailable):
            raise
        return None
    return coordinator


async def async_setup_entry(hass: HomeAssistant, entry: MeteoFranceConfigEntry) -> None:
    """Set up a Meteo-France account from a config entry."""
    departments_with_alert = hass.data.setdefault(METEO_FRANCE_DATA, set())

    client = MeteoFranceClient()

    async def _async_close_session() -> None:
        await hass.async_add_executor_job(client.session.close)

    entry.async_on_unload(_async_close_session)

    coordinator_forecast = MeteoFranceForecastUpdateCoordinator(hass, entry, client)
    coordinator_alert = None

    await coordinator_forecast.async_config_entry_first_refresh()

    coordinator_rain = await _async_get_rain_coordinator(hass, entry, client)

    department = coordinator_forecast.data.position.get("dept")
    _LOGGER.debug(
        "Department corresponding to %s is %s",
        entry.title,
        department,
    )
    if department is not None and is_valid_warning_department(department):
        if department not in departments_with_alert:
            coordinator_alert = MeteoFranceAlertUpdateCoordinator(
                hass,
                entry,
                client,
                department,
            )

            await coordinator_alert.async_config_entry_first_refresh()
            departments_with_alert.add(department)
        else:
            _LOGGER.warning(
                (
                    "Weather alert for department %s won't be added with city %s, as it"
                    " has already been added within another city"
                ),
                department,
                entry.title,
            )
    else:
        _LOGGER.warning(
            (
                "Weather alert not available: The city %s is not in metropolitan France"
                " or Andorre"
            ),
            entry.title,
        )

    entry.runtime_data = MeteoFranceData(
        forecast_coordinator=coordinator_forecast,
        rain_coordinator=coordinator_rain,
        alert_coordinator=coordinator_alert,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: MeteoFranceConfigEntry
) -> None:
    """Unload a config entry."""
    if entry.runtime_data.alert_coordinator:
        department = entry.runtime_data.forecast_coordinator.data.position.get("dept")
        hass.data[METEO_FRANCE_DATA].discard(department)
        _LOGGER.debug(
            (
                "Weather alert for depatment %s unloaded and released. It can be added"
                " now by another city"
            ),
            department,
        )

    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
