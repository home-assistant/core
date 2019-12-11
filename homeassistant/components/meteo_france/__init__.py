"""Support for Meteo-France weather data."""
import datetime
import logging

from meteofrance.client import meteofranceClient, meteofranceError
from vigilancemeteo import VigilanceMeteoError, VigilanceMeteoFranceProxy
import voluptuous as vol

from homeassistant.const import CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.util import Throttle

from .const import CONF_CITY, DATA_METEO_FRANCE, DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=5)


def has_all_unique_cities(value):
    """Validate that all cities are unique."""
    cities = [location[CONF_CITY] for location in value]
    vol.Schema(vol.Unique())(cities)
    return value


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Required(CONF_CITY): cv.string,
                        vol.Optional(CONF_MONITORED_CONDITIONS): vol.All(
                            cv.ensure_list, [vol.In(SENSOR_TYPES)]
                        ),
                    }
                )
            ],
            has_all_unique_cities,
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the Meteo-France component."""
    hass.data[DATA_METEO_FRANCE] = {}

    # Check if at least weather alert have to be monitored for one location.
    need_weather_alert_watcher = False
    for location in config[DOMAIN]:
        if (
            CONF_MONITORED_CONDITIONS in location
            and "weather_alert" in location[CONF_MONITORED_CONDITIONS]
        ):
            need_weather_alert_watcher = True

    # If weather alert monitoring is expected initiate a client to be used by
    # all weather_alert entities.
    if need_weather_alert_watcher:
        _LOGGER.debug("Weather Alert monitoring expected. Loading vigilancemeteo")

        weather_alert_client = VigilanceMeteoFranceProxy()
        try:
            weather_alert_client.update_data()
        except VigilanceMeteoError as exp:
            _LOGGER.error(
                "Unexpected error when creating the vigilance_meteoFrance proxy: %s ",
                exp,
            )
    else:
        weather_alert_client = None
    hass.data[DATA_METEO_FRANCE]["weather_alert_client"] = weather_alert_client

    for location in config[DOMAIN]:

        city = location[CONF_CITY]

        try:
            client = meteofranceClient(city)
        except meteofranceError as exp:
            _LOGGER.error(
                "Unexpected error when creating the meteofrance proxy: %s", exp
            )
            return

        client.need_rain_forecast = bool(
            CONF_MONITORED_CONDITIONS in location
            and "next_rain" in location[CONF_MONITORED_CONDITIONS]
        )

        hass.data[DATA_METEO_FRANCE][city] = MeteoFranceUpdater(client)
        hass.data[DATA_METEO_FRANCE][city].update()

        if CONF_MONITORED_CONDITIONS in location:
            monitored_conditions = location[CONF_MONITORED_CONDITIONS]
            _LOGGER.debug("meteo_france sensor platform loaded for %s", city)
            load_platform(
                hass,
                "sensor",
                DOMAIN,
                {CONF_CITY: city, CONF_MONITORED_CONDITIONS: monitored_conditions},
                config,
            )

        load_platform(hass, "weather", DOMAIN, {CONF_CITY: city}, config)

    return True


class MeteoFranceUpdater:
    """Update data from Meteo-France."""

    def __init__(self, client):
        """Initialize the data object."""
        self._client = client

    def get_data(self):
        """Get the latest data from Meteo-France."""
        return self._client.get_data()

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data from Meteo-France."""

        try:
            self._client.update()
        except meteofranceError as exp:
            _LOGGER.error(
                "Unexpected error when updating the meteofrance proxy: %s", exp
            )
