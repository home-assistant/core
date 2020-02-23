"""Support for August devices."""
import asyncio
from datetime import timedelta
from functools import partial
import logging

from august.api import Api, AugustApiHTTPError
from august.authenticator import AuthenticationState, Authenticator, ValidationResult
from requests import RequestException, Session
import voluptuous as vol

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

_CONFIGURING = {}

DEFAULT_TIMEOUT = 10
ACTIVITY_FETCH_LIMIT = 10
ACTIVITY_INITIAL_FETCH_LIMIT = 20

CONF_LOGIN_METHOD = "login_method"
CONF_INSTALL_ID = "install_id"

NOTIFICATION_ID = "august_notification"
NOTIFICATION_TITLE = "August Setup"

AUGUST_CONFIG_FILE = ".august.conf"

DATA_AUGUST = "august"
DOMAIN = "august"
DEFAULT_ENTITY_NAMESPACE = "august"

# Limit battery, online, and hardware updates to 1800 seconds
# in order to reduce the number of api requests and
# avoid hitting rate limits
MIN_TIME_BETWEEN_LOCK_DETAIL_UPDATES = timedelta(seconds=1800)

# Doorbells need to update more frequently than locks
# since we get an image from the doorbell api. Once
# py-august 0.18.0 is released doorbell status updates
# can be reduced in the same was as locks have been
MIN_TIME_BETWEEN_DOORBELL_DETAIL_UPDATES = timedelta(seconds=20)

# Activity needs to be checked more frequently as the
# doorbell motion and rings are included here
MIN_TIME_BETWEEN_ACTIVITY_UPDATES = timedelta(seconds=10)

DEFAULT_SCAN_INTERVAL = timedelta(seconds=10)


LOGIN_METHODS = ["phone", "email"]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_LOGIN_METHOD): vol.In(LOGIN_METHODS),
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_INSTALL_ID): cv.string,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

AUGUST_COMPONENTS = ["camera", "binary_sensor", "lock"]


def request_configuration(hass, config, api, authenticator, token_refresh_lock):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator

    def august_configuration_callback(data):
        """Run when the configuration callback is called."""

        result = authenticator.validate_verification_code(data.get("verification_code"))

        if result == ValidationResult.INVALID_VERIFICATION_CODE:
            configurator.notify_errors(
                _CONFIGURING[DOMAIN], "Invalid verification code"
            )
        elif result == ValidationResult.VALIDATED:
            setup_august(hass, config, api, authenticator, token_refresh_lock)

    if DOMAIN not in _CONFIGURING:
        authenticator.send_verification_code()

    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    login_method = conf.get(CONF_LOGIN_METHOD)

    _CONFIGURING[DOMAIN] = configurator.request_config(
        NOTIFICATION_TITLE,
        august_configuration_callback,
        description=f"Please check your {login_method} ({username}) and enter the verification code below",
        submit_caption="Verify",
        fields=[
            {"id": "verification_code", "name": "Verification code", "type": "string"}
        ],
    )


def setup_august(hass, config, api, authenticator, token_refresh_lock):
    """Set up the August component."""

    authentication = None
    try:
        authentication = authenticator.authenticate()
    except RequestException as ex:
        _LOGGER.error("Unable to connect to August service: %s", str(ex))

        hass.components.persistent_notification.create(
            "Error: {ex}<br />You will need to restart hass after fixing.",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )

    state = authentication.state

    if state == AuthenticationState.AUTHENTICATED:
        if DOMAIN in _CONFIGURING:
            hass.components.configurator.request_done(_CONFIGURING.pop(DOMAIN))

        hass.data[DATA_AUGUST] = AugustData(
            hass, api, authentication, authenticator, token_refresh_lock
        )

        for component in AUGUST_COMPONENTS:
            discovery.load_platform(hass, component, DOMAIN, {}, config)

        return True
    if state == AuthenticationState.BAD_PASSWORD:
        _LOGGER.error("Invalid password provided")
        return False
    if state == AuthenticationState.REQUIRES_VALIDATION:
        request_configuration(hass, config, api, authenticator, token_refresh_lock)
        return True

    return False


async def async_setup(hass, config):
    """Set up the August component."""

    conf = config[DOMAIN]
    api_http_session = None
    try:
        api_http_session = Session()
    except RequestException as ex:
        _LOGGER.warning("Creating HTTP session failed with: %s", str(ex))

    api = Api(timeout=conf.get(CONF_TIMEOUT), http_session=api_http_session)

    authenticator = Authenticator(
        api,
        conf.get(CONF_LOGIN_METHOD),
        conf.get(CONF_USERNAME),
        conf.get(CONF_PASSWORD),
        install_id=conf.get(CONF_INSTALL_ID),
        access_token_cache_file=hass.config.path(AUGUST_CONFIG_FILE),
    )

    def close_http_session(event):
        """Close API sessions used to connect to August."""
        _LOGGER.debug("Closing August HTTP sessions")
        if api_http_session:
            try:
                api_http_session.close()
            except RequestException:
                pass

        _LOGGER.debug("August HTTP session closed.")

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, close_http_session)
    _LOGGER.debug("Registered for Home Assistant stop event")

    token_refresh_lock = asyncio.Lock()

    return await hass.async_add_executor_job(
        setup_august, hass, config, api, authenticator, token_refresh_lock
    )


class AugustData:
    """August data object."""

    def __init__(self, hass, api, authentication, authenticator, token_refresh_lock):
        """Init August data object."""
        self._hass = hass
        self._api = api
        self._authenticator = authenticator
        self._access_token = authentication.access_token
        self._access_token_expires = authentication.access_token_expires

        self._token_refresh_lock = token_refresh_lock
        self._doorbells = self._api.get_doorbells(self._access_token) or []
        self._locks = self._api.get_operable_locks(self._access_token) or []
        self._house_ids = set()
        for device in self._doorbells + self._locks:
            self._house_ids.add(device.house_id)

        self._doorbell_detail_by_id = {}
        self._lock_detail_by_id = {}
        self._activities_by_id = {}

        # We check the locks right away so we can
        # remove inoperative ones
        self._update_locks_detail()

        self._filter_inoperative_locks()

    @property
    def house_ids(self):
        """Return a list of house_ids."""
        return self._house_ids

    @property
    def doorbells(self):
        """Return a list of doorbells."""
        return self._doorbells

    @property
    def locks(self):
        """Return a list of locks."""
        return self._locks

    async def _async_refresh_access_token_if_needed(self):
        """Refresh the august access token if needed."""
        if self._authenticator.should_refresh():
            async with self._token_refresh_lock:
                await self._hass.async_add_executor_job(self._refresh_access_token)

    def _refresh_access_token(self):
        refreshed_authentication = self._authenticator.refresh_access_token(force=False)
        _LOGGER.info(
            "Refreshed august access token. The old token expired at %s, and the new token expires at %s",
            self._access_token_expires,
            refreshed_authentication.access_token_expires,
        )
        self._access_token = refreshed_authentication.access_token
        self._access_token_expires = refreshed_authentication.access_token_expires

    async def async_get_device_activities(self, device_id, *activity_types):
        """Return a list of activities."""
        _LOGGER.debug("Getting device activities for %s", device_id)
        await self._async_update_device_activities()

        activities = self._activities_by_id.get(device_id, [])
        if activity_types:
            return [a for a in activities if a.activity_type in activity_types]
        return activities

    async def async_get_latest_device_activity(self, device_id, *activity_types):
        """Return latest activity."""
        activities = await self.async_get_device_activities(device_id, *activity_types)
        return next(iter(activities or []), None)

    @Throttle(MIN_TIME_BETWEEN_ACTIVITY_UPDATES)
    async def _async_update_device_activities(self, limit=ACTIVITY_FETCH_LIMIT):
        """Update data object with latest from August API."""

        # This is the only place we refresh the api token
        await self._async_refresh_access_token_if_needed()
        return await self._hass.async_add_executor_job(
            partial(self._update_device_activities, limit=ACTIVITY_FETCH_LIMIT)
        )

    def _update_device_activities(self, limit=ACTIVITY_FETCH_LIMIT):
        _LOGGER.debug("Start retrieving device activities")
        for house_id in self.house_ids:
            _LOGGER.debug("Updating device activity for house id %s", house_id)

            activities = self._api.get_house_activities(
                self._access_token, house_id, limit=limit
            )

            device_ids = {a.device_id for a in activities}
            for device_id in device_ids:
                self._activities_by_id[device_id] = [
                    a for a in activities if a.device_id == device_id
                ]

        _LOGGER.debug("Completed retrieving device activities")

    async def async_get_doorbell_detail(self, device_id):
        """Return doorbell detail."""
        await self._async_update_doorbells_detail()
        return self._doorbell_detail_by_id.get(device_id)

    @Throttle(MIN_TIME_BETWEEN_DOORBELL_DETAIL_UPDATES)
    async def _async_update_doorbells_detail(self):
        await self._hass.async_add_executor_job(self._update_doorbells_detail)

    def _update_doorbells_detail(self):
        self._doorbell_detail_by_id = self._update_device_detail(
            "doorbell", self._doorbells, self._api.get_doorbell_detail
        )

    def lock_has_doorsense(self, device_id):
        """Determine if a lock has doorsense installed and can tell when the door is open or closed."""
        # We do not update here since this is not expected
        # to change until restart
        if self._lock_detail_by_id[device_id] is None:
            return False
        return self._lock_detail_by_id[device_id].doorsense

    async def async_get_lock_detail(self, device_id):
        """Return lock detail."""
        await self._async_update_locks_detail()
        return self._lock_detail_by_id[device_id]

    def get_lock_name(self, device_id):
        """Return lock name as August has it stored."""
        for lock in self._locks:
            if lock.device_id == device_id:
                return lock.device_name

    @Throttle(MIN_TIME_BETWEEN_LOCK_DETAIL_UPDATES)
    async def _async_update_locks_detail(self):
        await self._hass.async_add_executor_job(self._update_locks_detail)

    def _update_locks_detail(self):
        self._lock_detail_by_id = self._update_device_detail(
            "lock", self._locks, self._api.get_lock_detail
        )

    def _update_device_detail(self, device_type, devices, api_call):
        detail_by_id = {}

        _LOGGER.debug("Start retrieving %s detail", device_type)
        for device in devices:
            device_id = device.device_id
            try:
                detail_by_id[device_id] = api_call(self._access_token, device_id)
            except RequestException as ex:
                _LOGGER.error(
                    "Request error trying to retrieve %s details for %s. %s",
                    device_type,
                    device.device_name,
                    ex,
                )
                detail_by_id[device_id] = None
            except Exception:
                detail_by_id[device_id] = None
                raise

        _LOGGER.debug("Completed retrieving %s detail", device_type)
        return detail_by_id

    def lock(self, device_id):
        """Lock the device."""
        return _call_api_operation_that_requires_bridge(
            self.get_lock_name(device_id),
            "lock",
            self._api.lock_return_activities,
            self._access_token,
            device_id,
        )

    def unlock(self, device_id):
        """Unlock the device."""
        return _call_api_operation_that_requires_bridge(
            self.get_lock_name(device_id),
            "unlock",
            self._api.unlock_return_activities,
            self._access_token,
            device_id,
        )

    def _filter_inoperative_locks(self):
        # Remove non-operative locks as there must
        # be a bridge (August Connect) for them to
        # be usable
        operative_locks = []
        for lock in self._locks:
            lock_detail = self._lock_detail_by_id.get(lock.device_id)
            if lock_detail is None:
                _LOGGER.info(
                    "The lock %s could not be setup because the system could not fetch details about the lock.",
                    lock.device_name,
                )
            elif lock_detail.bridge is None:
                _LOGGER.info(
                    "The lock %s could not be setup because it does not have a bridge (Connect).",
                    lock.device_name,
                )
            elif not lock_detail.bridge.operative:
                _LOGGER.info(
                    "The lock %s could not be setup because the bridge (Connect) is not operative.",
                    lock.device_name,
                )
            else:
                operative_locks.append(lock)

        self._locks = operative_locks


def _call_api_operation_that_requires_bridge(
    device_name, operation_name, func, *args, **kwargs
):
    """Call an API that requires the bridge to be online."""
    ret = None
    try:
        ret = func(*args, **kwargs)
    except AugustApiHTTPError as err:
        raise HomeAssistantError(device_name + ": " + str(err))

    return ret
