"""
Support for August devices.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/august/
"""

import logging
from datetime import timedelta

import voluptuous as vol
from requests import RequestException

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, CONF_TIMEOUT)
from homeassistant.helpers import discovery
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

_CONFIGURING = {}

REQUIREMENTS = ['py-august==0.4.0']

DEFAULT_TIMEOUT = 10
ACTIVITY_FETCH_LIMIT = 10
ACTIVITY_INITIAL_FETCH_LIMIT = 20

CONF_LOGIN_METHOD = 'login_method'
CONF_INSTALL_ID = 'install_id'

NOTIFICATION_ID = 'august_notification'
NOTIFICATION_TITLE = "August Setup"

AUGUST_CONFIG_FILE = '.august.conf'

DATA_AUGUST = 'august'
DOMAIN = 'august'
DEFAULT_ENTITY_NAMESPACE = 'august'
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)
DEFAULT_SCAN_INTERVAL = timedelta(seconds=5)
LOGIN_METHODS = ['phone', 'email']

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_LOGIN_METHOD): vol.In(LOGIN_METHODS),
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_INSTALL_ID): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    })
}, extra=vol.ALLOW_EXTRA)

AUGUST_COMPONENTS = [
    'camera', 'binary_sensor', 'lock'
]


def request_configuration(hass, config, api, authenticator):
    """Request configuration steps from the user."""
    configurator = hass.components.configurator

    def august_configuration_callback(data):
        """Run when the configuration callback is called."""
        from august.authenticator import ValidationResult

        result = authenticator.validate_verification_code(
            data.get('verification_code'))

        if result == ValidationResult.INVALID_VERIFICATION_CODE:
            configurator.notify_errors(_CONFIGURING[DOMAIN],
                                       "Invalid verification code")
        elif result == ValidationResult.VALIDATED:
            setup_august(hass, config, api, authenticator)

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
        submit_caption='Verify',
        fields=[{
            'id': 'verification_code',
            'name': "Verification code",
            'type': 'string'}]
    )


def setup_august(hass, config, api, authenticator):
    """Set up the August component."""
    from august.authenticator import AuthenticationState

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
            notification_id=NOTIFICATION_ID)

    state = authentication.state

    if state == AuthenticationState.AUTHENTICATED:
        if DOMAIN in _CONFIGURING:
            hass.components.configurator.request_done(_CONFIGURING.pop(DOMAIN))

        hass.data[DATA_AUGUST] = AugustData(api, authentication.access_token)

        for component in AUGUST_COMPONENTS:
            discovery.load_platform(hass, component, DOMAIN, {}, config)

        return True
    if state == AuthenticationState.BAD_PASSWORD:
        return False
    if state == AuthenticationState.REQUIRES_VALIDATION:
        request_configuration(hass, config, api, authenticator)
        return True

    return False


def setup(hass, config):
    """Set up the August component."""
    from august.api import Api
    from august.authenticator import Authenticator

    conf = config[DOMAIN]
    api = Api(timeout=conf.get(CONF_TIMEOUT))

    authenticator = Authenticator(
        api,
        conf.get(CONF_LOGIN_METHOD),
        conf.get(CONF_USERNAME),
        conf.get(CONF_PASSWORD),
        install_id=conf.get(CONF_INSTALL_ID),
        access_token_cache_file=hass.config.path(AUGUST_CONFIG_FILE))

    return setup_august(hass, config, api, authenticator)


class AugustData:
    """August data object."""

    def __init__(self, api, access_token):
        """Init August data object."""
        self._api = api
        self._access_token = access_token
        self._doorbells = self._api.get_doorbells(self._access_token) or []
        self._locks = self._api.get_operable_locks(self._access_token) or []
        self._house_ids = [d.house_id for d in self._doorbells + self._locks]

        self._doorbell_detail_by_id = {}
        self._lock_status_by_id = {}
        self._lock_detail_by_id = {}
        self._activities_by_id = {}

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

    def get_device_activities(self, device_id, *activity_types):
        """Return a list of activities."""
        self._update_device_activities()

        activities = self._activities_by_id.get(device_id, [])
        if activity_types:
            return [a for a in activities if a.activity_type in activity_types]
        return activities

    def get_latest_device_activity(self, device_id, *activity_types):
        """Return latest activity."""
        activities = self.get_device_activities(device_id, *activity_types)
        return next(iter(activities or []), None)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def _update_device_activities(self, limit=ACTIVITY_FETCH_LIMIT):
        """Update data object with latest from August API."""
        for house_id in self.house_ids:
            activities = self._api.get_house_activities(self._access_token,
                                                        house_id,
                                                        limit=limit)

            device_ids = {a.device_id for a in activities}
            for device_id in device_ids:
                self._activities_by_id[device_id] = [a for a in activities if
                                                     a.device_id == device_id]

    def get_doorbell_detail(self, doorbell_id):
        """Return doorbell detail."""
        self._update_doorbells()
        return self._doorbell_detail_by_id.get(doorbell_id)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def _update_doorbells(self):
        detail_by_id = {}

        for doorbell in self._doorbells:
            detail_by_id[doorbell.device_id] = self._api.get_doorbell_detail(
                self._access_token, doorbell.device_id)

        self._doorbell_detail_by_id = detail_by_id

    def get_lock_status(self, lock_id):
        """Return lock status."""
        self._update_locks()
        return self._lock_status_by_id.get(lock_id)

    def get_lock_detail(self, lock_id):
        """Return lock detail."""
        self._update_locks()
        return self._lock_detail_by_id.get(lock_id)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def _update_locks(self):
        status_by_id = {}
        detail_by_id = {}

        for lock in self._locks:
            status_by_id[lock.device_id] = self._api.get_lock_status(
                self._access_token, lock.device_id)
            detail_by_id[lock.device_id] = self._api.get_lock_detail(
                self._access_token, lock.device_id)

        self._lock_status_by_id = status_by_id
        self._lock_detail_by_id = detail_by_id

    def lock(self, device_id):
        """Lock the device."""
        return self._api.lock(self._access_token, device_id)

    def unlock(self, device_id):
        """Unlock the device."""
        return self._api.unlock(self._access_token, device_id)
