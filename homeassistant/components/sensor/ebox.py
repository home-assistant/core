"""
Support for EBox.

Get data from 'My Usage Page' page:
https://client.ebox.ca/myusage

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.ebox/
"""
import logging
from datetime import timedelta

import requests
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_USERNAME, CONF_PASSWORD,
    CONF_NAME, CONF_MONITORED_VARIABLES)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['beautifulsoup4==4.5.1']

_LOGGER = logging.getLogger(__name__)

GIGABITS = "Gb"  # type: str
PRICE = "CAD"  # type: str
DAYS = "days"  # type: str
PERCENT = "%"  # type: str

DEFAULT_NAME = "EBox"

REQUESTS_TIMEOUT = 15
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

SENSOR_TYPES = {
    'usage': ['Usage',
              PERCENT, 'mdi:percent'],
    'balance': ['Balance',
                PRICE, 'mdi:square-inc-cash'],
    'limit': ['Data limit',
              GIGABITS, 'mdi:download'],
    'days_left': ['Days left',
                  DAYS, 'mdi:calendar-today'],
    'before_offpeak_download': ['Download before offpeak',
                                GIGABITS, 'mdi:download'],
    'before_offpeak_upload': ['Upload before offpeak',
                              GIGABITS, 'mdi:upload'],
    'before_offpeak_total': ['Total before offpeak',
                             GIGABITS, 'mdi:download'],
    'offpeak_download': ['Offpeak download',
                         GIGABITS, 'mdi:download'],
    'offpeak_upload': ['Offpeak Upload',
                       GIGABITS, 'mdi:upload'],
    'offpeak_total': ['Offpeak Total',
                      GIGABITS, 'mdi:download'],
    'download': ['Download',
                 GIGABITS, 'mdi:download'],
    'upload': ['Upload',
               GIGABITS, 'mdi:upload'],
    'total': ['Total',
              GIGABITS, 'mdi:download'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_VARIABLES):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

HOST = "https://client.ebox.ca"
HOME_URL = "{}/".format(HOST)
LOGIN_URL = "{}/login".format(HOST)
USAGE_URL = "{}/myusage".format(HOST)

USAGE_MAP = {"before_offpeak_download": 0,
             "before_offpeak_upload": 1,
             "before_offpeak_total": 2,
             "offpeak_download": 3,
             "offpeak_upload": 4,
             "offpeak_total": 5,
             "download": 6,
             "upload": 7,
             "total": 8}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the EBox sensor."""
    # Create a data fetcher to support all of the configured sensors. Then make
    # the first call to init the data.

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    try:
        ebox_data = EBoxData(username, password)
        ebox_data.update()
    except requests.exceptions.HTTPError as error:
        _LOGGER.error(error)
        return False

    name = config.get(CONF_NAME)

    sensors = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        sensors.append(EBoxSensor(ebox_data, variable, name))

    add_devices(sensors)


class EBoxSensor(Entity):
    """Implementation of a EBox sensor."""

    def __init__(self, ebox_data, sensor_type, name):
        """Initialize the sensor."""
        self.client_name = name
        self.type = sensor_type
        self.entity_id = "sensor.{}_{}".format(name, sensor_type)
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self.ebox_data = ebox_data
        self._state = None

        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    def update(self):
        """Get the latest data from EBox and update the state."""
        self.ebox_data.update()
        if self.type in self.ebox_data.data:
            self._state = round(self.ebox_data.data[self.type], 2)


class EBoxData(object):
    """Get data from HydroQuebec."""

    def __init__(self, username, password):
        """Initialize the data object."""
        self.username = username
        self.password = password
        self.data = {}
        self.cookies = None

    def _get_login_page(self):
        """Go to the login page."""
        from bs4 import BeautifulSoup
        try:
            raw_res = requests.get(HOME_URL, timeout=REQUESTS_TIMEOUT)
        except OSError:
            _LOGGER.error("Can not connect to login page")
            return False
        # Get cookies
        self.cookies = raw_res.cookies
        # Get token
        soup = BeautifulSoup(raw_res.content, 'html.parser')
        token_node = soup.find('input', {'name': '_csrf_security_token'})
        if token_node is None:
            _LOGGER.error("No token input found")
            return False
        token = token_node.attrs.get('value')
        if token is None:
            _LOGGER.error("No token found")
            return False
        return token

    def _post_login_page(self, token):
        """Login to EBox website."""
        data = {"usrname": self.username,
                "pwd": self.password,
                "_csrf_security_token": token}

        try:
            raw_res = requests.post(LOGIN_URL,
                                    data=data,
                                    cookies=self.cookies,
                                    allow_redirects=False,
                                    timeout=REQUESTS_TIMEOUT)
        except OSError:
            _LOGGER.error("Can not submit login form")
            return False
        if raw_res.status_code != 302:
            _LOGGER.error("Bad HTTP status code")
            return False

        # Update cookies
        self.cookies.update(raw_res.cookies)
        return True

    def _get_home_data(self):
        """Get home data."""
        # Import
        from bs4 import BeautifulSoup
        # Prepare return
        home_data = {}
        # Http request
        try:
            raw_res = requests.get(HOME_URL,
                                   cookies=self.cookies,
                                   timeout=REQUESTS_TIMEOUT)
        except OSError:
            _LOGGER.error("Can not get home page")
            return False
        # Update cookies
        self.cookies.update(raw_res.cookies)
        # Prepare soup
        soup = BeautifulSoup(raw_res.content, 'html.parser')
        # Looking for limit
        limit_node = soup.find('span', {'class': 'text_summary3'})
        if limit_node is None:
            _LOGGER.error("Can not found limit span")
            return False
        raw_data = [d.strip() for d in limit_node.text.split("/")]
        if len(raw_data) != 2:
            _LOGGER.error("Can not get limit data")
            return False
        try:
            home_data["limit"] = float(raw_data[1].split()[0])
        except OSError:
            _LOGGER.error("Can not get limit data")
            return False
        # Get balance
        try:
            str_value = soup.find("div", {"class": "text_amount"}).\
                            text.split()[0]
            home_data["balance"] = float(str_value)
        except OSError:
            _LOGGER.error("Can not get current balance")
            return False
        # Get percent
        try:
            str_value = soup.find("div", {"id": "circleprogress_0"}).\
                            attrs.get("data-perc")
            home_data["usage"] = float(str_value)
        except OSError:
            _LOGGER.error("Can not get usage percent")
            return False
        return home_data

    def _get_usage_data(self):
        """Get data usage."""
        # Import
        from bs4 import BeautifulSoup
        # Get Usage
        raw_res = requests.get(USAGE_URL, cookies=self.cookies)
        soup = BeautifulSoup(raw_res.content, 'html.parser')
        # Find all span
        span_list = soup.find_all("span", {"class": "switchDisplay"})
        if span_list is None:
            _LOGGER.error("Can not get usage page")
            return False
        usage_data = {}
        # Get data
        for key, index in USAGE_MAP.items():
            try:
                str_value = span_list[index].attrs.get("data-m").split()[0]
                usage_data[key] = abs(float(str_value)) / 1024
            except OSError:
                _LOGGER.error("Can not get %s", key)
                return False
        return usage_data

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from HydroQuebec."""
        # Get login page
        token = self._get_login_page()
        if not token:
            return
        # Post login page
        if not self._post_login_page(token):
            return
        # Get home data
        home_data = self._get_home_data()
        if not home_data:
            return
        # Get usage data
        usage_data = self._get_usage_data()
        if not usage_data:
            return
        # merge data
        self.data.update(home_data)
        self.data.update(usage_data)
