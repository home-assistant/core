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
from homeassistant.util import Throttle, dt

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

# Limit battery and hardware updates to 1800 seconds
# in order to reduce the number of api requests and
# avoid hitting rate limits
MIN_TIME_BETWEEN_LOCK_DETAIL_UPDATES = timedelta(seconds=1800)

# Limit locks status check to 900 seconds now that
# we get the state from the lock and unlock api calls
# and the lock and unlock activities are now captured
MIN_TIME_BETWEEN_LOCK_STATUS_UPDATES = timedelta(seconds=900)

# Doorbells need to update more frequently than locks
# since we get an image from the doorbell api
MIN_TIME_BETWEEN_DOORBELL_STATUS_UPDATES = timedelta(seconds=20)

# Activity needs to be checked more frequently as the
# doorbell motion and rings are included here
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)

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
        description="Please check your {} ({}) and enter the verification "
        "code below".format(login_method, username),
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
            "Error: {}<br />"
            "You will need to restart hass after fixing."
            "".format(ex),
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
        self._door_last_state_update_time_utc_by_id = {}
        self._lock_last_status_update_time_utc_by_id = {}
        self._lock_status_by_id = {}
        self._lock_detail_by_id = {}
        self._door_state_by_id = {}
        self._activities_by_id = {}

        # We check the locks right away so we can
        # remove inoperative ones
        self._update_locks_status()
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

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
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

    async def async_get_doorbell_detail(self, doorbell_id):
        """Return doorbell detail."""
        await self._async_update_doorbells()
        return self._doorbell_detail_by_id.get(doorbell_id)

    @Throttle(MIN_TIME_BETWEEN_DOORBELL_STATUS_UPDATES)
    async def _async_update_doorbells(self):
        await self._hass.async_add_executor_job(self._update_doorbells)

    def _update_doorbells(self):
        detail_by_id = {}

        _LOGGER.debug("Start retrieving doorbell details")
        for doorbell in self._doorbells:
            _LOGGER.debug("Updating doorbell status for %s", doorbell.device_name)
            try:
                detail_by_id[doorbell.device_id] = self._api.get_doorbell_detail(
                    self._access_token, doorbell.device_id
                )
            except RequestException as ex:
                _LOGGER.error(
                    "Request error trying to retrieve doorbell status for %s. %s",
                    doorbell.device_name,
                    ex,
                )
                detail_by_id[doorbell.device_id] = None
            except Exception:
                detail_by_id[doorbell.device_id] = None
                raise

        _LOGGER.debug("Completed retrieving doorbell details")
        self._doorbell_detail_by_id = detail_by_id

    def update_door_state(self, lock_id, door_state, update_start_time_utc):
        """Set the door status and last status update time.

        This is called when newer activity is detected on the activity feed
        in order to keep the internal data in sync
        """
        self._door_state_by_id[lock_id] = door_state
        self._door_last_state_update_time_utc_by_id[lock_id] = update_start_time_utc
        return True

    def update_lock_status(self, lock_id, lock_status, update_start_time_utc):
        """Set the lock status and last status update time.

        This is used when the lock, unlock apis are called
        or newer activity is detected on the activity feed
        in order to keep the internal data in sync
        """
        self._lock_status_by_id[lock_id] = lock_status
        self._lock_last_status_update_time_utc_by_id[lock_id] = update_start_time_utc
        return True

    def lock_has_doorsense(self, lock_id):
        """Determine if a lock has doorsense installed and can tell when the door is open or closed."""
        # We do not update here since this is not expected
        # to change until restart
        if self._lock_detail_by_id[lock_id] is None:
            return False
        return self._lock_detail_by_id[lock_id].doorsense

    async def async_get_lock_status(self, lock_id):
        """Return status if the door is locked or unlocked.

        This is status for the lock itself.
        """
        await self._async_update_locks()
        return self._lock_status_by_id.get(lock_id)

    async def async_get_lock_detail(self, lock_id):
        """Return lock detail."""
        await self._async_update_locks()
        return self._lock_detail_by_id.get(lock_id)

    def get_lock_name(self, device_id):
        """Return lock name as August has it stored."""
        for lock in self._locks:
            if lock.device_id == device_id:
                return lock.device_name

    async def async_get_door_state(self, lock_id):
        """Return status if the door is open or closed.

        This is the status from the door sensor.
        """
        await self._async_update_locks_status()
        return self._door_state_by_id.get(lock_id)

    async def _async_update_locks(self):
        await self._async_update_locks_status()
        await self._async_update_locks_detail()

    @Throttle(MIN_TIME_BETWEEN_LOCK_STATUS_UPDATES)
    async def _async_update_locks_status(self):
        await self._hass.async_add_executor_job(self._update_locks_status)

    def _update_locks_status(self):
        status_by_id = {}
        state_by_id = {}
        lock_last_status_update_by_id = {}
        door_last_state_update_by_id = {}

        _LOGGER.debug("Start retrieving lock and door status")
        for lock in self._locks:
            update_start_time_utc = dt.utcnow()
            _LOGGER.debug("Updating lock and door status for %s", lock.device_name)
            try:
                (
                    status_by_id[lock.device_id],
                    state_by_id[lock.device_id],
                ) = self._api.get_lock_status(
                    self._access_token, lock.device_id, door_status=True
                )
                # Since there is a a race condition between calling the
                # lock and activity apis, we set the last update time
                # BEFORE making the api call since we will compare this
                # to activity later we want activity to win over stale lock/door
                # state.
                lock_last_status_update_by_id[lock.device_id] = update_start_time_utc
                door_last_state_update_by_id[lock.device_id] = update_start_time_utc
            except RequestException as ex:
                _LOGGER.error(
                    "Request error trying to retrieve lock and door status for %s. %s",
                    lock.device_name,
                    ex,
                )
                status_by_id[lock.device_id] = None
                state_by_id[lock.device_id] = None
            except Exception:
                status_by_id[lock.device_id] = None
                state_by_id[lock.device_id] = None
                raise

        _LOGGER.debug("Completed retrieving lock and door status")
        self._lock_status_by_id = status_by_id
        self._door_state_by_id = state_by_id
        self._door_last_state_update_time_utc_by_id = door_last_state_update_by_id
        self._lock_last_status_update_time_utc_by_id = lock_last_status_update_by_id

    def get_last_lock_status_update_time_utc(self, lock_id):
        """Return the last time that a lock status update was seen from the august API."""
        # Since the activity api is called more frequently than
        # the lock api it is possible that the lock has not
        # been updated yet
        if lock_id not in self._lock_last_status_update_time_utc_by_id:
            return dt.utc_from_timestamp(0)

        return self._lock_last_status_update_time_utc_by_id[lock_id]

    def get_last_door_state_update_time_utc(self, lock_id):
        """Return the last time that a door status update was seen from the august API."""
        # Since the activity api is called more frequently than
        # the lock api it is possible that the door has not
        # been updated yet
        if lock_id not in self._door_last_state_update_time_utc_by_id:
            return dt.utc_from_timestamp(0)

        return self._door_last_state_update_time_utc_by_id[lock_id]

    @Throttle(MIN_TIME_BETWEEN_LOCK_DETAIL_UPDATES)
    async def _async_update_locks_detail(self):
        await self._hass.async_add_executor_job(self._update_locks_detail)

    def _update_locks_detail(self):
        detail_by_id = {}

        _LOGGER.debug("Start retrieving locks detail")
        for lock in self._locks:
            try:
                detail_by_id[lock.device_id] = self._api.get_lock_detail(
                    self._access_token, lock.device_id
                )
            except RequestException as ex:
                _LOGGER.error(
                    "Request error trying to retrieve door details for %s. %s",
                    lock.device_name,
                    ex,
                )
                detail_by_id[lock.device_id] = None
            except Exception:
                detail_by_id[lock.device_id] = None
                raise

        _LOGGER.debug("Completed retrieving locks detail")
        self._lock_detail_by_id = detail_by_id

    def lock(self, device_id):
        """Lock the device."""
        return _call_api_operation_that_requires_bridge(
            self.get_lock_name(device_id),
            "lock",
            self._api.lock,
            self._access_token,
            device_id,
        )

    def unlock(self, device_id):
        """Unlock the device."""
        return _call_api_operation_that_requires_bridge(
            self.get_lock_name(device_id),
            "unlock",
            self._api.unlock,
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
