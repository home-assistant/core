"""The FMI (Finnish Meteorological Institute) component."""

from datetime import date, datetime

from async_timeout import timeout
from dateutil import tz
import fmi_weather_client as fmi
from fmi_weather_client.errors import ClientError, ServerError

from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_OFFSET,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    _LOGGER,
    COORDINATOR,
    DOMAIN,
    FMI_WEATHER_SYMBOL_MAP,
    MIN_TIME_BETWEEN_UPDATES,
    UNDO_UPDATE_LISTENER,
)

PLATFORMS = ["weather"]


def base_unique_id(latitude, longitude):
    """Return unique id for entries in configuration."""
    return f"{latitude}_{longitude}"


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured FMI."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass, config_entry) -> bool:
    """Set up FMI as config entry."""
    latitude = config_entry.data[CONF_LATITUDE]
    longitude = config_entry.data[CONF_LONGITUDE]
    time_step = config_entry.options.get(CONF_OFFSET, False)

    _LOGGER.debug("Using lat: %s and long: %s", latitude, longitude)

    websession = async_get_clientsession(hass)

    coordinator = FMIDataUpdateCoordinator(
        hass, websession, latitude, longitude, time_step
    )
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    undo_listener = config_entry.add_update_listener(update_listener)

    hass.data[DOMAIN][config_entry.entry_id] = {
        COORDINATOR: coordinator,
        UNDO_UPDATE_LISTENER: undo_listener,
    }

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass, config_entry):
    """Unload an FMI config entry."""
    for component in PLATFORMS:
        await hass.config_entries.async_forward_entry_unload(config_entry, component)

    hass.data[DOMAIN][config_entry.entry_id][UNDO_UPDATE_LISTENER]()
    hass.data[DOMAIN].pop(config_entry.entry_id)

    return True


async def update_listener(hass, config_entry):
    """Update FMI listener."""
    await hass.config_entries.async_reload(config_entry.entry_id)


class FMIDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching FMI data API."""

    def __init__(self, hass, session, latitude, longitude, time_step):
        """Initialize."""
        self.latitude = latitude
        self.longitude = longitude
        self.unique_id = str(self.latitude) + ":" + str(self.longitude)
        self.time_step = time_step
        self.current = None
        self.forecast = None
        self._hass = hass

        _LOGGER.debug("Data will be updated every %s min", MIN_TIME_BETWEEN_UPDATES)

        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=MIN_TIME_BETWEEN_UPDATES
        )

    async def _async_update_data(self):
        """Update data via Open API."""
        try:
            async with timeout(10):
                self.current = await self._hass.async_add_executor_job(
                    fmi.weather_by_coordinates, self.latitude, self.longitude
                )
                self.forecast = await self._hass.async_add_executor_job(
                    fmi.forecast_by_coordinates,
                    self.latitude,
                    self.longitude,
                    self.time_step,
                )
        except (ClientError, ServerError) as error:
            raise UpdateFailed(error) from error
        return {}


def get_weather_symbol(symbol, hass=None):
    """Get a weather symbol for the symbol value."""
    ret_val = ""
    if symbol in FMI_WEATHER_SYMBOL_MAP.keys():
        ret_val = FMI_WEATHER_SYMBOL_MAP[symbol]
        if hass is not None and ret_val == 1:  # Clear as per FMI
            today = date.today()
            sunset = get_astral_event_date(hass, SUN_EVENT_SUNSET, today)
            sunset = sunset.astimezone(tz.tzlocal())

            if datetime.now().astimezone(tz.tzlocal()) >= sunset:
                # Clear night
                ret_val = FMI_WEATHER_SYMBOL_MAP[0]
    return ret_val
