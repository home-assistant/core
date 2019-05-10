"""Sensor for Suez Water Consumption data."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, VOLUME_LITERS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)
CONF_COUNTER_ID = 'counter_id'

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)
SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_COUNTER_ID): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the sensor platform."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    counter_id = config.get(CONF_COUNTER_ID)
    _LOGGER.debug(
        "Username is %s and counter_id is %s.",
        username, counter_id
        )
    add_devices([SuezClient(username, password, counter_id)], True)


class SuezClient(Entity):
    """Global variables."""

    BASE_URI = 'https://www.toutsurmoneau.fr'
    API_ENDPOINT_LOGIN = '/mon-compte-en-ligne/je-me-connecte'
    API_ENDPOINT_DATA = '/mon-compte-en-ligne/statJData/'
    API_ENDPOINT_HISTORY = '/mon-compte-en-ligne/statMData/'

    """Representation of a Sensor."""

    def __init__(self, username, password, counter_id):
        """Initialize the data object."""
        self._name = "Suez Water Client"
        self._username = username
        self._password = password
        self._counter_id = counter_id
        self._token = ''
        self._headers = {}
        self._attributes = {}
        self.data = {}
        self.success = False
        self._state = 0
        self._icon = 'mdi:water-pump'

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return VOLUME_LITERS

    @property
    def state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

    def _get_token(self):
        import requests
        import re
        headers = {
            'Accept': "application/json, text/javascript, */*; q=0.01",
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept-Language': 'fr,fr-FR;q=0.8,en;q=0.6',
            'User-Agent': 'curl/7.54.0',
            'Connection': 'keep-alive',
            'Cookie': ''
        }

        url = self.BASE_URI+self.API_ENDPOINT_LOGIN

        response = requests.get(url, headers=headers)

        headers['Cookie'] = ""
        for key in response.cookies.get_dict():
            if headers['Cookie']:
                headers['Cookie'] += "; "
            headers['Cookie'] += key + "=" + response.cookies[key]

        phrase = re.compile('_csrf_token" value="(.*)" />')
        result = phrase.search(response.content.decode('utf-8'))
        self._token = result.group(1)
        _LOGGER.debug("Le token is %s", self._token)
        self._headers = headers

    def _get_cookie(self):
        import requests
        login = requests.Session()
        data = {
            '_username': self._username,
            '_password': self._password,
            '_csrf_token': self._token,
            'signin[username]': self._username,
            'signin[password]': None,
            'tsme_user_login[_username]': self._username,
            'tsme_user_login[_password]': self._password
                }
        url = self.BASE_URI+self.API_ENDPOINT_LOGIN
        login.post(url, headers=self._headers, data=data)
        _LOGGER.debug("Cookie is %s", login.cookies.get("eZSESSID"))
        self._headers['Cookie'] = ''
        self._headers['Cookie'] = 'eZSESSID='+login.cookies.get("eZSESSID")

    def _fetch_data(self):
        """Fetch latest data from Suez."""
        import datetime
        import requests
        now = datetime.datetime.now()
        today_year = now.strftime("%Y")
        today_month = now.strftime("%m")
        yesterday = datetime.datetime.now() - datetime.timedelta(1)
        yesterday_year = yesterday.strftime('%Y')
        yesterday_month = yesterday.strftime('%m')
        yesterday_day = yesterday.strftime('%d')
        url = self.BASE_URI+self.API_ENDPOINT_DATA
        url += '{}/{}/{}'.format(
            yesterday_year,
            yesterday_month, self._counter_id
            )

        data = requests.get(url, headers=self._headers)

        try:
            self._state = int(float(data.json()[int(
                yesterday_day)-1][1])*1000)
            self.success = True

        except ValueError:
            _LOGGER.debug("Issue with this yesterday data")
            pass

        try:
            if yesterday_month != today_month:
                url = self.BASE_URI+self.API_ENDPOINT_DATA
                url += '{}/{}/{}'.format(
                    today_year,
                    today_month, self._counter_id
                    )
                _LOGGER.debug("Getting data for previous month")
                data = requests.get(url, headers=self._headers)

            self._attributes['thisMonthConsumption'] = {}
            for item in data.json():
                self._attributes['thisMonthConsumption'][item[0]] = int(
                    float(item[1])*1000)

        except ValueError:
            _LOGGER.debug("Issue with this month data")
            pass

        try:
            if int(today_month) == 1:
                last_month = 12
                last_month_year = int(today_year) - 1
            else:
                last_month = int(today_month) - 1
                last_month_year = today_year

            url = self.BASE_URI+self.API_ENDPOINT_DATA
            url += '{}/{}/{}'.format(
                last_month_year, last_month,
                self._counter_id
                )

            _LOGGER.debug("Getting data for previous month")
            data = requests.get(url, headers=self._headers)

            self._attributes['previousMonthConsumption'] = {}
            for item in data.json():
                self._attributes['previousMonthConsumption'][item[0]] = int(
                    float(item[1])*1000)

        except ValueError:
            _LOGGER.debug("Issue with this previous month data")
            pass

        try:
            url = self.BASE_URI+self.API_ENDPOINT_HISTORY
            url += '{}'.format(self._counter_id)

            data = requests.get(url, headers=self._headers)
            fetched_data = data.json()
            self._attributes['highestMonthlyConsumption'] = int(
                float(fetched_data[-1])*1000)
            fetched_data.pop()
            self._attributes['lastYearOverAll'] = int(
                float(fetched_data[-1])*1000)
            fetched_data.pop()
            self._attributes['thisYearOverAll'] = int(
                float(fetched_data[-1])*1000)
            fetched_data.pop()
            self._attributes['history'] = {}
            for item in fetched_data:
                self._attributes['history'][item[3]] = int(
                    float(item[1])*1000)

            _LOGGER.debug("_attributes est %s", self._attributes)

        except ValueError:
            _LOGGER.debug("Issue with history data")
            raise

    def update(self):
        """Return the latest collected data from Linky."""
        self._get_token()
        self._get_cookie()
        self._fetch_data()
        if not self.success:
            return
        _LOGGER.debug("Suez data state is: %s", self._state)
