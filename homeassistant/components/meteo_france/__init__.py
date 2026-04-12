"""Support for Meteo-France weather data."""

import logging

from meteofrance_api.client import MeteoFranceClient
from meteofrance_api.helpers import is_valid_warning_department
from requests import RequestException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import (
    COORDINATOR_ALERT,
    COORDINATOR_FORECAST,
    COORDINATOR_RAIN,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import (
    MeteoFranceAlertUpdateCoordinator,
    MeteoFranceForecastUpdateCoordinator,
    MeteoFranceRainUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Meteo-France account from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client = MeteoFranceClient()

    coordinator_forecast = MeteoFranceForecastUpdateCoordinator(hass, entry, client)
    coordinator_rain = None
    coordinator_alert = None

    # Fetch initial data so we have data when entities subscribe
    await coordinator_forecast.async_refresh()

    if not coordinator_forecast.last_update_success:
        raise ConfigEntryNotReady

    # Check rain forecast.
    coordinator_rain = MeteoFranceRainUpdateCoordinator(hass, entry, client)
    try:
        await coordinator_rain._async_refresh(log_failures=False)  # noqa: SLF001
    except RequestException:
        _LOGGER.warning(
            "1 hour rain forecast not available: %s is not in covered zone",
            entry.title,
        )

    department = coordinator_forecast.data.position.get("dept")
    _LOGGER.debug(
        "Department corresponding to %s is %s",
        entry.title,
        department,
    )
    if department is not None and is_valid_warning_department(department):
        if not hass.data[DOMAIN].get(department):
            coordinator_alert = MeteoFranceAlertUpdateCoordinator(
                hass,
                entry,
                client,
                department,
            )

            await coordinator_alert.async_refresh()

            if coordinator_alert.last_update_success:
                hass.data[DOMAIN][department] = True
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

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR_FORECAST: coordinator_forecast,
    }
    if coordinator_rain and coordinator_rain.last_update_success:
        hass.data[DOMAIN][entry.entry_id][COORDINATOR_RAIN] = coordinator_rain
    if coordinator_alert and coordinator_alert.last_update_success:
        hass.data[DOMAIN][entry.entry_id][COORDINATOR_ALERT] = coordinator_alert

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if hass.data[DOMAIN][entry.entry_id][COORDINATOR_ALERT]:
        department = hass.data[DOMAIN][entry.entry_id][
            COORDINATOR_FORECAST
        ].data.position.get("dept")
        hass.data[DOMAIN][department] = False
        _LOGGER.debug(
            (
                "Weather alert for depatment %s unloaded and released. It can be added"
                " now by another city"
            ),
            department,
        )

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
