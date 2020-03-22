"""The Schluter DITRA-HEAT integration."""
from datetime import timedelta
import logging
import pickle

from requests import RequestException, Session
from schluter.api import Api
from schluter.authenticator import AuthenticationState, Authenticator
import voluptuous as vol

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
DATA_SCHLUTER = "schluter"
PLATFORMS = ["climate"]
DEFAULT_TIMEOUT = 10
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)
SCHLUTER_CONFIG_FILE = ".schluter.conf"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_schluter(hass, config, api, authenticator):
    """Set up the Schluter component."""

    authentication = None
    try:
        authentication = authenticator.authenticate()
    except RequestException as ex:
        _LOGGER.error("Unable to connect to Schluter service: %s", ex)

    state = authentication.state

    if state == AuthenticationState.AUTHENTICATED:

        async def async_update_data():
            try:
                return api.get_thermostats(authentication.session_id) or []
            except RequestException as err:
                raise UpdateFailed(f"Error communicating with Schluter API: {err}")

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name="schluter",
            update_method=async_update_data,
            update_interval=timedelta(seconds=30),
        )

        await coordinator.async_refresh()

        hass.data[DATA_SCHLUTER] = SchluterData(
            hass, api, authentication.session_id, coordinator
        )

        for component in PLATFORMS:
            discovery.load_platform(hass, component, DOMAIN, {}, config)

        return True
    if state == AuthenticationState.BAD_PASSWORD:
        _LOGGER.error("Invalid password provided")
        return False
    if state == AuthenticationState.BAD_EMAIL:
        _LOGGER.error("Invalid email provided")
        return False

    return False


async def async_setup(hass, config):
    """Set up the Schluter component."""
    _LOGGER.debug("Starting setup of schluter")
    conf = config[DOMAIN]
    api_http_session = None
    try:
        api_http_session = Session()
    except RequestException as ex:
        _LOGGER.warning("Creating HTTP session failed with: %s", ex)

    api = Api(timeout=conf.get(CONF_TIMEOUT), http_session=api_http_session)

    authenticator = Authenticator(
        api,
        conf.get(CONF_USERNAME),
        conf.get(CONF_PASSWORD),
        session_id_cache_file=hass.config.path(SCHLUTER_CONFIG_FILE),
    )

    # def close_http_session(event):
    #     """Close API sessions used to connect to Schluter."""
    #     _LOGGER.debug("Closing HTTP sessions")
    #     if api_http_session:
    #         try:
    #             api_http_session.close()
    #         except RequestException:
    #             pass

    #     _LOGGER.debug("HTTP session closed.")

    # hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, close_http_session)
    # _LOGGER.debug("Registered for Home Assistant stop event")

    return await async_setup_schluter(hass, config, api, authenticator)


class SchluterData:
    """Schluter data object."""

    def __init__(self, hass, api, session_id, coordinator):
        """Initialize Schluter data."""
        self._hass = hass
        self._api = api
        self._session_id = session_id
        self._coordinator = coordinator
        self._thermostats = coordinator.data

    @property
    def thermostats(self):
        """Get thermostats."""
        return self._thermostats

    @property
    def coordinator(self):
        return self._coordinator

    async def async_update(self):
        await self._coordinator.async_request_refresh()

    # def get_thermostat_temp(self, serial_number):
    #     """Get thermostat current temperatures."""
    #     self._update_thermostats()
    #     return self._thermostat_temp_by_id.get(serial_number)

    # def get_thermostat_set_temp(self, serial_number):
    #     """Get thermostat set temperatures."""
    #     self._update_thermostats()
    #     return self._thermostat_set_temp_by_id.get(serial_number)

    # def get_thermostat_heating_status(self, serial_number):
    #     """Get thermostat heating statuses."""
    #     self._update_thermostats()
    #     return self._thermostat_is_heating_by_id.get(serial_number)

    # def set_thermostat_temp(self, serial_number, temperature):
    #     """Set thermostat temperature.."""
    #     result = self._api.set_temperature(self._session_id, serial_number, temperature)
    #     return result

    # @Throttle(MIN_TIME_BETWEEN_UPDATES)
    # def _update_thermostats(self):
    #     temp_by_id = {}
    #     set_temp_by_id = {}
    #     is_heating_by_id = {}

    #     try:
    #         _LOGGER.debug("Updating thermostats from API")
    #         self._thermostats = self._api.get_thermostats(self._session_id)

    #         for thermostat in self._thermostats:
    #             temp_by_id[thermostat.serial_number] = thermostat.temperature
    #             set_temp_by_id[thermostat.serial_number] = thermostat.set_point_temp
    #             is_heating_by_id[thermostat.serial_number] = thermostat.is_heating
    #     except RequestException as ex:
    #         _LOGGER.error("Request error trying to retrieve thermostats. %s", ex)

    #     _LOGGER.debug("Successfully retrieved thermostats from API")
    #     self._thermostat_temp_by_id = temp_by_id
    #     self._thermostat_set_temp_by_id = set_temp_by_id
    #     self._thermostat_is_heating_by_id = is_heating_by_id
