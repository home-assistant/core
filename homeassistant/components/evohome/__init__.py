"""Support for (EMEA/EU-based) Honeywell evohome (TCC) systems.

Glossary:
TCS - temperature control system (a.k.a. Controller, Parent), which can have up
to 13 Children:
- 0-12 Heating zones (a.k.a. Zone), Climate devices, and
- 0-1 DHW controller (a.k.a. Boiler), a WaterHeater device
"""
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any, Awaitable, Dict, Optional, Tuple, List

import requests.exceptions
import voluptuous as vol
import evohomeclient2

from homeassistant.const import (
    CONF_SCAN_INTERVAL, CONF_USERNAME, CONF_PASSWORD,
    EVENT_HOMEASSISTANT_START,
    HTTP_SERVICE_UNAVAILABLE, HTTP_TOO_MANY_REQUESTS,
    PRECISION_HALVES, TEMP_CELSIUS,
    CONF_ACCESS_TOKEN, CONF_ACCESS_TOKEN_EXPIRES, CONF_REFRESH_TOKEN)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect, async_dispatcher_send)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import (
    async_track_point_in_utc_time, async_track_time_interval)

from .const import (
    DOMAIN, STORAGE_VERSION, STORAGE_KEY, GWS, TCS)

_LOGGER = logging.getLogger(__name__)

CONF_LOCATION_IDX = 'location_idx'
SCAN_INTERVAL_DEFAULT = timedelta(seconds=300)
SCAN_INTERVAL_MINIMUM = timedelta(seconds=180)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_LOCATION_IDX, default=0): cv.positive_int,
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL_DEFAULT):
            vol.All(cv.time_period, vol.Range(min=SCAN_INTERVAL_MINIMUM)),
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, hass_config):
    """Create a (EMEA/EU-based) Honeywell evohome system."""
    broker = EvoBroker(hass, hass_config[DOMAIN])
    if not await broker.init_client():
        return False

    async_track_time_interval(
        hass,
        broker.update,
        timedelta(seconds=10)
        # self.params[CONF_SCAN_INTERVAL]                                        # TODO: restore this
    )

    load_platform(hass, 'climate', DOMAIN, {}, hass_config)
    if broker.tcs.hotwater:
        load_platform(hass, 'water_heater', DOMAIN, {}, hass_config)

    return True


class EvoBroker:
    """Container for evohome client and data."""

    def __init__(self, hass, params):
        """Initialize the evohome client and data structure."""
        self.hass = hass
        self.params = params

        self.config = self.status = self.timers = {}

        self.client = None
        self._app_storage = None

        hass.data[DOMAIN] = {}
        hass.data[DOMAIN]['broker'] = self

    async def init_client(self) -> bool:
        """Initialse the evohome data broker.

        Return True if this is successful, otherwise return False.
        """
        refresh_token, access_token, access_token_expires = \
            await self._load_auth_tokens()

        try:
            client = self.client = await self.hass.async_add_executor_job(
                evohomeclient2.EvohomeClient,
                self.params[CONF_USERNAME],
                self.params[CONF_PASSWORD],
                False,
                refresh_token,
                access_token,
                access_token_expires
            )

        except evohomeclient2.AuthenticationError as err:
            _LOGGER.error(
                "Failed to authenticate with the vendor's server. "
                "Check your username and password are correct. "
                "Resolve any errors and restart HA. Message is: %s",
                err
            )
            return False

        except requests.exceptions.ConnectionError:
            _LOGGER.error(
                "Unable to connect with the vendor's server. "
                "Check your network and the vendor's status page. "
                "Resolve any errors and restart HA."
            )
            return False

        else:
            await self._save_auth_tokens()

        finally:  # Redact any config data that's not needed/not to be logged
            self.params[CONF_PASSWORD] = 'REDACTED'

        # Pull down the installation configuration
        loc_idx = self.params[CONF_LOCATION_IDX]
        try:
            self.config = client.installation_info[loc_idx][GWS][0][TCS][0]

        except IndexError:
            _LOGGER.error(
                "Config error: '%s' = %s, but its valid range is 0-%s. "
                "Unable to continue. "
                "Fix any configuration errors and restart HA.",
                CONF_LOCATION_IDX, loc_idx, len(client.installation_info) - 1
            )
            return False

        else:
            self.tcs = \
                client.locations[loc_idx]._gateways[0]._control_systems[0]  # noqa: E501; pylint: disable=protected-access

        _LOGGER.debug("Config = %s", self.config)

        return True

    async def _load_auth_tokens(self) -> Tuple[str, str, datetime]:
        store = self.hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        app_storage = self._app_storage = await store.async_load()

        if app_storage.get(CONF_USERNAME) == self.params[CONF_USERNAME]:
            refresh_token = app_storage.get(CONF_REFRESH_TOKEN)
            access_token = app_storage.get(CONF_ACCESS_TOKEN)
            access_token_expires = app_storage.get(CONF_ACCESS_TOKEN_EXPIRES)
            if access_token_expires:
                access_token_expires = datetime.strptime(
                    access_token_expires, '%Y-%m-%d %H:%M:%S')
            return (refresh_token, access_token, access_token_expires)

        return (None, None, None)  # account switched: so tokens are not valid

    async def _save_auth_tokens(self) -> None:
        self._app_storage[CONF_USERNAME] = self.params[CONF_USERNAME]
        self._app_storage[CONF_REFRESH_TOKEN] = self.client.refresh_token
        self._app_storage[CONF_ACCESS_TOKEN] = self.client.access_token
        self._app_storage[CONF_ACCESS_TOKEN_EXPIRES] = \
            self.client.access_token_expires.strftime('%Y-%m-%d %H:%M:%S')

        _LOGGER.warn("AAA expires = %s", self.client.access_token_expires)
        _LOGGER.warn("AAA time    = %s", datetime.now())

        store = self.hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        await store.async_save(self._app_storage)

    def update(self, args, **kwargs):
        """Get the latest state data of the entire evohome Location.

        This includes state data for the Controller and all its child devices,
        such as the operating mode of the Controller and the current temp of
        its children (e.g. Zones, DHW controller).
        """
        loc_idx = self.params[CONF_LOCATION_IDX]

        try:
            status = self.client.locations[loc_idx].status()[GWS][0][TCS][0]
        except (requests.exceptions.RequestException,
                evohomeclient2.AuthenticationError) as err:
            self._handle_exception(err)
        else:
            self.timers['statusUpdated'] = datetime.now()

        _LOGGER.debug("Status = %s", status)

        async_track_point_in_utc_time(                                           # TODO: add code to _save_auth_tokens
            self.hass,
            self._save_auth_tokens,
            self.client.access_token_expires + timedelta(minutes=1)
        )

        # inform the evohome devices that state data has been updated
        async_dispatcher_send(self.hass, DOMAIN, {'signal': 'refresh'})


class EvoDevice(Entity):
    """Base for any Honeywell evohome device.

    Such devices include the Controller, (up to 12) Heating Zones and
    (optionally) a DHW controller.
    """

    def __init__(self, evo_broker, evo_device):
        """Initialize the evohome entity."""
        self._evo_device = evo_device
        self._evo_tcs = evo_broker.tcs

        self._config = self._status = {}

        self._id = self._name = self._icon = self._precision = None
        self._operation_list = self._supported_features = None
        self._available = False  # should become True after first update()

    @callback
    def _refresh(self, packet):
        if packet['signal'] == 'refresh':
            self.async_schedule_update_ha_state(force_refresh=True)

    def _handle_exception(self, err):
        try:
            raise err

        except evohomeclient2.AuthenticationError:
            _LOGGER.error(
                "Failed to (re)authenticate with the vendor's server. "
                "Message is: %s",
                err
            )

        except requests.exceptions.ConnectionError:
            # this appears to be common with Honeywell's servers
            _LOGGER.warning(
                "Unable to connect with the vendor's server. "
                "Check your network and the vendor's status page."
            )

        except requests.exceptions.HTTPError:
            if err.response.status_code == HTTP_SERVICE_UNAVAILABLE:
                _LOGGER.warning(
                    "Vendor says their server is currently unavailable. "
                    "Check the vendor's status page."
                )

            elif err.response.status_code == HTTP_TOO_MANY_REQUESTS:
                _LOGGER.warning(
                    "The vendor's API rate limit has been exceeded. "
                    "Consider increasing the %s.", CONF_SCAN_INTERVAL
                )

            else:
                raise  # we don't expect/handle any other HTTPErrors

    @property
    def should_poll(self) -> bool:
        """The evohome devices should not be polled."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the Evohome entity."""
        return self._name

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the Evohome-specific state attributes."""
        status = {}
        for attr in self._state_attributes:
            status[attr] = getattr(self._evo_device, attr)
        return {'status': status}

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend UI."""
        return self._icon

    @property
    def available(self) -> bool:
        """Return True if the device is currently available."""
        return self._available

    @property
    def supported_features(self) -> int:
        """Get the flag of supported features of the device."""
        return self._supported_features

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        async_dispatcher_connect(self.hass, DOMAIN, self._refresh)

    @property
    def precision(self) -> float:
        """Return the temperature precision to use in the frontend UI."""
        return self._precision

    @property
    def temperature_unit(self) -> str:
        """Return the temperature unit to use in the frontend UI."""
        return TEMP_CELSIUS

    @property
    def operation_list(self):
        """Return the list of available operations."""
        return self._operation_list
