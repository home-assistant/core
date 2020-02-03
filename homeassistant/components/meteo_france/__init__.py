"""Support for Meteo-France weather data."""
import datetime
import logging

from meteofrance.client import meteofranceClient, meteofranceError
from vigilancemeteo import VigilanceMeteoError, VigilanceMeteoFranceProxy
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util import Throttle

from .const import CONF_CITY, DOMAIN, SENSOR_TYPES

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=5)


CITY_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CITY): cv.string,
        vol.Optional(CONF_MONITORED_CONDITIONS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_TYPES)]
        ),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [CITY_SCHEMA]))}, extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up Meteo-France from legacy config file."""

    conf = config.get(DOMAIN)
    if conf is None:
        return True

    for city_conf in conf:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=city_conf.copy()
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up an Meteo-France account from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Check if at least weather alert have to be monitored for one location/entry.
    # If weather alert monitoring is expected initiate a client to be used by all weather_alert entities.
    if (
        CONF_MONITORED_CONDITIONS in entry.data
        and "weather_alert" in entry.data[CONF_MONITORED_CONDITIONS]
        and hass.data[DOMAIN].get("weather_alert_client") is not None
    ):
        _LOGGER.debug("Weather Alert monitoring expected. Loading vigilancemeteo")

        weather_alert_client = await hass.async_add_executor_job(
            VigilanceMeteoFranceProxy
        )
        try:
            weather_alert_client.update_data()
        except VigilanceMeteoError as exp:
            _LOGGER.error(
                "Unexpected error when creating the vigilance_meteoFrance proxy: %s ",
                exp,
            )
    else:
        weather_alert_client = None
    hass.data[DOMAIN]["weather_alert_client"] = weather_alert_client

    city = entry.data[CONF_CITY]

    try:
        client = await hass.async_add_executor_job(meteofranceClient, city)
    except meteofranceError as exp:
        _LOGGER.error("Unexpected error when creating the meteofrance proxy: %s", exp)
        return False

    client.need_rain_forecast = bool(
        CONF_MONITORED_CONDITIONS in entry.data
        and "next_rain" in entry.data[CONF_MONITORED_CONDITIONS]
    )

    hass.data[DOMAIN][city] = MeteoFranceUpdater(client)
    hass.data[DOMAIN][city].update()

    if CONF_MONITORED_CONDITIONS in entry.data:
        _LOGGER.debug("meteo_france sensor platform loaded for %s", city)
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "sensor")
        )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "weather")
    )
    return True


class MeteoFranceUpdater:
    """Update data from Meteo-France."""

    def __init__(self, client: meteofranceClient):
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
