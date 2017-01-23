"""
Support for HydroQuebec.

Get data from 'My Consumption Profile' page:
https://www.hydroquebec.com/portail/en/group/clientele/portrait-de-consommation

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.hydroquebec/
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

REQUIREMENTS = ['beautifulsoup4==4.5.3']

_LOGGER = logging.getLogger(__name__)

KILOWATT_HOUR = "kWh"  # type: str
PRICE = "CAD"  # type: str
DAYS = "days"  # type: str

DEFAULT_NAME = "HydroQuebec"

REQUESTS_TIMEOUT = 15
MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)

SENSOR_TYPES = {
    'period_total_bill': ['Current period bill',
                          PRICE, 'mdi:square-inc-cash'],
    'period_length': ['Current period length',
                      DAYS, 'mdi:calendar-today'],
    'period_total_days': ['Total number of days in this period',
                          DAYS, 'mdi:calendar-today'],
    'period_mean_daily_bill': ['Period daily average bill',
                               PRICE, 'mdi:square-inc-cash'],
    'period_mean_daily_consumption': ['Period daily average consumption',
                                      KILOWATT_HOUR, 'mdi:flash'],
    'period_total_consumption': ['Total Consumption',
                                 KILOWATT_HOUR, 'mdi:flash'],
    'period_lower_price_consumption': ['Period Lower price consumption',
                                       KILOWATT_HOUR, 'mdi:flash'],
    'period_higher_price_consumption': ['Period Higher price consumption',
                                        KILOWATT_HOUR, 'mdi:flash'],
    'yesterday_total_consumption': ['Yesterday total consumption',
                                    KILOWATT_HOUR, 'mdi:flash'],
    'yesterday_lower_price_consumption': ['Yesterday lower price consumption',
                                          KILOWATT_HOUR, 'mdi:flash'],
    'yesterday_higher_price_consumption':
    ['Yesterday higher price consumption', KILOWATT_HOUR, 'mdi:flash'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_VARIABLES):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

HOST = "https://www.hydroquebec.com"
HOME_URL = "{}/portail/web/clientele/authentification".format(HOST)
PROFILE_URL = ("{}/portail/fr/group/clientele/"
               "portrait-de-consommation".format(HOST))
MONTHLY_MAP = (('period_total_bill', 'montantFacturePeriode'),
               ('period_length', 'nbJourLecturePeriode'),
               ('period_total_days', 'nbJourPrevuPeriode'),
               ('period_mean_daily_bill', 'moyenneDollarsJourPeriode'),
               ('period_mean_daily_consumption', 'moyenneKwhJourPeriode'),
               ('period_total_consumption', 'consoTotalPeriode'),
               ('period_lower_price_consumption', 'consoRegPeriode'),
               ('period_higher_price_consumption', 'consoHautPeriode'))
DAILY_MAP = (('yesterday_total_consumption', 'consoTotalQuot'),
             ('yesterday_lower_price_consumption', 'consoRegQuot'),
             ('yesterday_higher_price_consumption', 'consoHautQuot'))


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the HydroQuebec sensor."""
    # Create a data fetcher to support all of the configured sensors. Then make
    # the first call to init the data.

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    try:
        hydroquebec_data = HydroquebecData(username, password)
        hydroquebec_data.update()
    except requests.exceptions.HTTPError as error:
        _LOGGER.error(error)
        return False

    name = config.get(CONF_NAME)

    sensors = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        sensors.append(HydroQuebecSensor(hydroquebec_data, variable, name))

    add_devices(sensors)


class HydroQuebecSensor(Entity):
    """Implementation of a HydroQuebec sensor."""

    def __init__(self, hydroquebec_data, sensor_type, name):
        """Initialize the sensor."""
        self.client_name = name
        self.type = sensor_type
        self.entity_id = "sensor.{}_{}".format(name, sensor_type)
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self.hydroquebec_data = hydroquebec_data
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
        """Get the latest data from Hydroquebec and update the state."""
        self.hydroquebec_data.update()
        self._state = round(self.hydroquebec_data.data[self.type], 2)


class HydroquebecData(object):
    """Get data from HydroQuebec."""

    def __init__(self, username, password):
        """Initialize the data object."""
        self.username = username
        self.password = password
        self.data = None
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
        # Get login url
        soup = BeautifulSoup(raw_res.content, 'html.parser')
        form_node = soup.find('form', {'name': 'fm'})
        if form_node is None:
            _LOGGER.error("No login form find")
            return False
        login_url = form_node.attrs.get('action')
        if login_url is None:
            _LOGGER.error("Can not found login url")
            return False
        return login_url

    def _post_login_page(self, login_url):
        """Login to HydroQuebec website."""
        data = {"login": self.username,
                "_58_password": self.password}

        try:
            raw_res = requests.post(login_url,
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

    def _get_p_p_id(self):
        """Get id of consumption profile."""
        from bs4 import BeautifulSoup
        try:
            raw_res = requests.get(PROFILE_URL,
                                   cookies=self.cookies,
                                   timeout=REQUESTS_TIMEOUT)
        except OSError:
            _LOGGER.error("Can not get profile page")
            return False
        # Update cookies
        self.cookies.update(raw_res.cookies)
        # Looking for p_p_id
        soup = BeautifulSoup(raw_res.content, 'html.parser')
        p_p_id = None
        for node in soup.find_all('span'):
            node_id = node.attrs.get('id', "")
            print(node_id)
            if node_id.startswith("p_portraitConsommation_WAR"):
                p_p_id = node_id[2:]
                break

        if p_p_id is None:
            _LOGGER.error("Could not get p_p_id")
            return False

        return p_p_id

    def _get_monthly_data(self, p_p_id):
        """Get monthly data."""
        params = {"p_p_id": p_p_id,
                  "p_p_lifecycle": 2,
                  "p_p_resource_id": ("resourceObtenirDonnees"
                                      "PeriodesConsommation")}
        try:
            raw_res = requests.get(PROFILE_URL,
                                   params=params,
                                   cookies=self.cookies,
                                   timeout=REQUESTS_TIMEOUT)
        except OSError:
            _LOGGER.error("Can not get monthly data")
            return False
        try:
            json_output = raw_res.json()
        except OSError:
            _LOGGER.error("Could not get monthly data")
            return False

        if not json_output.get('success'):
            _LOGGER.error("Could not get monthly data")
            return False

        return json_output.get('results')

    def _get_daily_data(self, p_p_id, start_date, end_date):
        """Get daily data."""
        params = {"p_p_id": p_p_id,
                  "p_p_lifecycle": 2,
                  "p_p_resource_id":
                  "resourceObtenirDonneesQuotidiennesConsommation",
                  "dateDebutPeriode": start_date,
                  "dateFinPeriode": end_date}
        try:
            raw_res = requests.get(PROFILE_URL,
                                   params=params,
                                   cookies=self.cookies,
                                   timeout=REQUESTS_TIMEOUT)
        except OSError:
            _LOGGER.error("Can not get daily data")
            return False
        try:
            json_output = raw_res.json()
        except OSError:
            _LOGGER.error("Could not get daily data")
            return False

        if not json_output.get('success'):
            _LOGGER.error("Could not get daily data")
            return False

        return json_output.get('results')

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from HydroQuebec."""
        # Get login page
        login_url = self._get_login_page()
        if not login_url:
            return
        # Post login page
        if not self._post_login_page(login_url):
            return
        # Get p_p_id
        p_p_id = self._get_p_p_id()
        if not p_p_id:
            return
        # Get Monthly data
        monthly_data = self._get_monthly_data(p_p_id)[0]
        if not monthly_data:
            return
        # Get daily data
        start_date = monthly_data.get('dateDebutPeriode')
        end_date = monthly_data.get('dateFinPeriode')
        daily_data = self._get_daily_data(p_p_id, start_date, end_date)
        if not daily_data:
            return
        daily_data = daily_data[0]['courant']

        # format data
        self.data = {}
        for key1, key2 in MONTHLY_MAP:
            self.data[key1] = monthly_data[key2]
        for key1, key2 in DAILY_MAP:
            self.data[key1] = daily_data[key2]
