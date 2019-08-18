"""Linky Atome."""
import logging

from datetime import timedelta

import pickle
import voluptuous as vol

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_TIMEOUT, CONF_NAME
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

import requests


_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "atome"
DEFAULT_UNIT = "W"
DEFAULT_CLASS = "power"

ATOME_COOKIE = "atome_cookies.pickle"
ATOME_USER_ID = "atome_user_id.pickle"
ATOME_USER_REFERENCE = "atome_user_reference.pickle"
SCAN_INTERVAL = timedelta(seconds=30)
SESSION_RENEW_INTERVAL = timedelta(minutes=55)
DEFAULT_TIMEOUT = 10


COOKIE_NAME = "PHPSESSID"
API_BASE_URI = "https://esoftlink.esoftthings.com"
API_ENDPOINT_LOGIN = "/api/user/login.json"
API_ENDPOINT_LIVE = "/measure/live.json"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor."""
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    timeout = config.get(CONF_TIMEOUT)

    # # LOGIN
    cookie_path = hass.config.path(ATOME_COOKIE)
    user_id_path = hass.config.path(ATOME_USER_ID)
    user_reference_path = hass.config.path(ATOME_USER_REFERENCE)

    add_entities(
        [
            AtomeSensor(
                name,
                username,
                password,
                timeout,
                cookie_path,
                user_id_path,
                user_reference_path,
            )
        ]
    )
    return True


class AtomeSensor(Entity):
    """Representation of a sensor entity for Atome."""

    def __init__(
        self,
        name,
        username,
        password,
        timeout,
        cookie_path,
        user_id_path,
        user_reference_path,
    ):
        """Initialize the sensor."""
        _LOGGER.debug("ATOME: INIT")
        self._name = name
        # self._unit = DEFAULT_UNIT
        self._unit_of_measurement = DEFAULT_UNIT
        self._device_class = DEFAULT_CLASS

        self._username = username
        self._password = password
        self._timeout = timeout

        self._cookie_path = cookie_path
        self._user_id_path = user_id_path
        self._user_reference_path = user_reference_path

        self._attributes = None
        self._state = None
        # self.update = Throttle(SCAN_INTERVAL)(self._update)
        # self.update()
        self._login(username, password)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name or DEFAULT_NAME

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def _load_file(self, filename):
        with open(filename, "rb") as f:
            return pickle.load(f)

    # @Throttle(SESSION_RENEW_INTERVAL)
    def _login(self, username, password):

        # Login the user into the Atome API.
        payload = {"email": username, "plainPassword": password}

        req = requests.post(
            API_BASE_URI + API_ENDPOINT_LOGIN,
            json=payload,
            headers={"content-type": "application/json"},
            timeout=self._timeout,
        )
        response_json = req.json()
        # _LOGGER.debug(response_json)
        session_cookie = req.cookies.get(COOKIE_NAME)

        if session_cookie is None:
            _LOGGER.exception("Login unsuccessful. Check your credentials")
            return False

        user_id = str(response_json["id"])
        user_reference = response_json["subscriptions"][0]["reference"]

        # store cookie
        with open(self._cookie_path, "wb") as f:
            pickle.dump(session_cookie, f)
        # store user id
        with open(self._user_id_path, "wb") as f:
            pickle.dump(user_id, f)
        # store user ref
        with open(self._user_reference_path, "wb") as f:
            pickle.dump(user_reference, f)

        _LOGGER.info(
            "ATOME: Successfully logged in to Atome API. User ID: [%s], User REF: [%s]",
            user_id,
            user_reference,
        )
        # /LOGIN
        return user_id, user_reference

    def _get_data(self, url):

        cookie = self._load_file(self._cookie_path)
        cookies = {COOKIE_NAME: cookie}

        req = requests.get(url, cookies=cookies, timeout=self._timeout)
        values = req.json()

        if req.status_code == 302:
            _LOGGER.warning("Unable to fetch Atome data: need to re-login! ")

        if req.status_code == 403:
            self._login(self._username, self._password)
            _LOGGER.warning("Unable to fetch Atome data: %s %s ", req.status_code, url)

        if req.status_code != 200:
            _LOGGER.warning("Unable to fetch Atome data: %s %s ", req.status_code, url)

        return values

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Update device state."""
        _LOGGER.debug("ATOME: Starting update of Atome Data")

        user_id = self._load_file(self._user_id_path)
        user_reference = self._load_file(self._user_reference_path)

        url = (
            API_BASE_URI
            + "/api/subscription/"
            + user_id
            + "/"
            + user_reference
            + API_ENDPOINT_LIVE
        )

        values = self._get_data(url)
        self._state = values["last"]

    #  TODO
    #  getData
    #  login
