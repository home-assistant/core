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

CONF_SECRETS = [
    CONF_PASSWORD,
    CONF_USERNAME,
]


async def async_setup(hass, hass_config):
    """Create a (EMEA/EU-based) Honeywell evohome system."""

    _LOGGER.warn("async_setup()")
    broker = EvoBroker(hass)
    _LOGGER.warn("broker=%s", broker)

    await broker.init_client(hass, hass_config)

    hass.data[DOMAIN]['client'] = broker._client

    async_track_time_interval(hass,
                              broker.update,
                              hass_config[DOMAIN][CONF_SCAN_INTERVAL])

    load_platform(hass, 'climate', DOMAIN, {}, hass_config)

    if 'dhw' in hass.data[DOMAIN]['config'][GWS][0][TCS][0]:
        load_platform(hass, 'water_heater', DOMAIN, {}, hass_config)

    @callback
    def _first_update(event):
        """When HA has started, the hub knows to retrieve it's first update."""
        async_dispatcher_send(hass, DOMAIN, {'signal': 'first_update'})

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, _first_update)

    return True


class EvoBroker:
    """Container for evohome client and data."""

    def __init__(self, hass):
        """Initialize the evohome client and data structure."""
        self.hass = hass
        self._client = None
        self._app_storage = None

        hass.data[DOMAIN] = {'config': {}, 'status': {}, 'timers': {}}

    async def init_client(self, hass, hass_config):

        _LOGGER.warn("init_client()")

        refresh_token, access_token, access_token_expires = \
            await self._load_auth_tokens(hass_config[DOMAIN][CONF_USERNAME])

        _LOGGER.warn("refresh_token %s", refresh_token)                              # TODO: for testing only
        _LOGGER.warn("access_token %s", access_token)                                # TODO: for testing only
        _LOGGER.warn("access_token_expires %s", access_token_expires)                # TODO: for testing only

        try:
            client = self._client = evohomeclient2.EvohomeClient(
                hass_config[DOMAIN][CONF_USERNAME],
                hass_config[DOMAIN][CONF_PASSWORD],
                refresh_token=refresh_token,
                access_token=access_token,
                access_token_expires=access_token_expires
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
            await self._save_auth_tokens(
                client.refresh_token,
                client.access_token,
                access_token_expires,
                username=hass_config[DOMAIN][CONF_USERNAME]
            )

            # async_track_point_in_utc_time(hass, _save_auth_tokens,
            #                               client.access_token_expires)

        # finally:  # Redact any config data that's not needed/not to be logged
        #     for parameter in CONF_SECRETS:
        #         evo_data['params'][parameter] = 'REDACTED' \
        #             if evo_data['params'][parameter] else None

#       evo_data = hass.data[DOMAIN] = {}
#       evo_data['timers'] = {}

#       evo_data['status'] = {}

        # Redact any installation data that's no longer needed
        for loc in client.installation_info:
            loc[GWS][0]['gatewayInfo'] = 'REDACTED'
            for key in ['locationId', 'locationOwner', 'streetAddress', 'city']:
                loc['locationInfo'][key] = 'REDACTED'

        # Pull down the installation configuration
        loc_idx = hass_config[DOMAIN][CONF_LOCATION_IDX]
        try:
            hass.data[DOMAIN]['config'] = client.installation_info[loc_idx]

        except IndexError:
            _LOGGER.error(
                "Config error: '%s' = %s, but its valid range is 0-%s. "
                "Unable to continue. Fix any configuration errors and restart HA.",
                CONF_LOCATION_IDX, loc_idx, len(client.installation_info) - 1
            )
            return False

        if _LOGGER.isEnabledFor(logging.DEBUG):
            tmp_loc = dict(hass.data[DOMAIN]['config'])
            tmp_loc['locationInfo']['postcode'] = 'REDACTED'

            _LOGGER.debug("hass.data[DOMAIN]['config']=%s", tmp_loc)

    async def _load_auth_tokens(self, username: str) -> Tuple[str, str, str]:
        _LOGGER.warn("_load_auth_tokens(AA)")
        store = self.hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        _LOGGER.warn("_load_auth_tokens(BB)")
        app_storage = self._app_storage = await store.async_load()
        _LOGGER.warn("_load_auth_tokens(CC)")

        if app_storage.get(CONF_USERNAME) == username:
            refresh_token = app_storage.get(CONF_REFRESH_TOKEN)
            access_token = app_storage.get(CONF_ACCESS_TOKEN)
            access_token_expires = app_storage.get(CONF_ACCESS_TOKEN_EXPIRES)
            if access_token_expires:
                access_token_expires = datetime.strptime(
                    access_token_expires, '%Y-%m-%d %H:%M:%S')
            return (refresh_token, access_token, access_token_expires)

        return (None, None, None)  # account switched: access token aint valid

    async def _save_auth_tokens(self,
                          refresh_token: str,
                          access_token: str,
                          access_token_expires: str,
                          username=None) -> None:
        self._app_storage[CONF_REFRESH_TOKEN] = refresh_token
        self._app_storage[CONF_ACCESS_TOKEN] = access_token
        self._app_storage[CONF_ACCESS_TOKEN_EXPIRES] = \
            access_token_expires.strftime('%Y-%m-%d %H:%M:%S')
        if username:
            self._app_storage[CONF_USERNAME] = username

        store = self.hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        await store.async_save(self._app_storage)

    async def async_update(self, now, **kwargs):
        """Update the evohome client's data."""
        try:
            await self._client.hub.update()
        except AssertionError:  # assert response.status == HTTP_OK
            _LOGGER.warning("Update failed.", exc_info=True)
            return
        async_dispatcher_send(self._hass, DOMAIN)

    def update(self):
        _LOGGER.warn("update()")


class EvoDevice(Entity):
    """Base for any Honeywell evohome device.

    Such devices include the Controller, (up to 12) Heating Zones and
    (optionally) a DHW controller.
    """

    def __init__(self, evo_data, client, evo_device):
        """Initialize the evohome entity."""
        self._client = client
        self._evo_device = evo_device

        self._id = None
        self._name = None
        self._icon = None
        self._precision = PRECISION_HALVES

        self._supported_features = None
        self._operation_list = None

        self._params = evo_data['params']
        self._timers = evo_data['timers']
        self._status = {}

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
                "This may be a temporary error. Message is: %s",
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
                    "This may be temporary; check the vendor's status page."
                )

            elif err.response.status_code == HTTP_TOO_MANY_REQUESTS:
                _LOGGER.warning(
                    "The vendor's API rate limit has been exceeded. "
                    "So will cease polling, and will resume after %s seconds.",
                    (self._params[CONF_SCAN_INTERVAL] * 3).total_seconds()
                )
                self._timers['statusUpdated'] = datetime.now() + \
                    self._params[CONF_SCAN_INTERVAL] * 3

            else:
                raise  # we don't expect/handle any other HTTPErrors

    @property
    def should_poll(self) -> bool:
        """Only the Evohome Controller should be polled."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the Evohome entity."""
        return self._name

    @property
    def device_state_attributes(self) -> Dict[str, Any]:
        """Return the Evohome-specific state attributes."""
        return {'status': self._status}

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
