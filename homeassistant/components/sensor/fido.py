"""
Support for Fido.

Get data from 'Usage Summary' page:
https://www.fido.ca/pages/#/my-account/wireless

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.fido/
"""
import json
import re
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

REQUIREMENTS = []

_LOGGER = logging.getLogger(__name__)

KILOBITS = "Kb"  # type: str
PRICE = "CAD"  # type: str
MESSAGES = "messages"  # type: str
MINUTES = "minutes"  # type: str

DEFAULT_NAME = "Fido"

REQUESTS_TIMEOUT = 15
MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=15)


SENSOR_TYPES = {
    'fido_dollar': ['Fido dollar',
                    PRICE, 'mdi:square-inc-cash'],
    'balance': ['Balance',
                PRICE, 'mdi:square-inc-cash'],
    'data_used': ['Data used',
                  KILOBITS, 'mdi:download'],
    'data_limit': ['Data limit',
                   KILOBITS, 'mdi:download'],
    'data_remaining': ['Data remaining',
                       KILOBITS, 'mdi:download'],
    'text_used': ['Text used',
                  MESSAGES, 'mdi:message-text'],
    'text_limit': ['Text limit',
                   MESSAGES, 'mdi:message-text'],
    'text_remaining': ['Text remaining',
                       MESSAGES, 'mdi:message-text'],
    'mms_used': ['MMS used',
                 MESSAGES, 'mdi:message-image'],
    'mms_limit': ['MMS limit',
                  MESSAGES, 'mdi:message-image'],
    'mms_remaining': ['MMS remaining',
                      MESSAGES, 'mdi:message-image'],
    'text_int_used': ['International text used',
                      MESSAGES, 'mdi:message-alert'],
    'text_int_limit': ['International text limit',
                       MESSAGES, 'mdi:message-alart'],
    'text_int_remaining': ['Internaltional remaining',
                           MESSAGES, 'mdi:message-alert'],
    'talk_used': ['Talk time',
                  MINUTES, 'mdi:cellphone'],
    'talk_limit': ['Talk time limit',
                   MINUTES, 'mdi:cellphone'],
    'talt_remaining': ['Talk time remaining',
                       MINUTES, 'mdi:cellphone'],
    'talk_other_used': ['Other Talk time',
                        MINUTES, 'mdi:cellphone'],
    'talk_other_limit': ['Other Talk time limit',
                         MINUTES, 'mdi:cellphone'],
    'talt_other_remaining': ['Other Talk time remaining',
                             MINUTES, 'mdi:cellphone'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_VARIABLES):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

JANRAIN_CLIENT_ID = "bfkecrvys7sprse8kc4wtwugr2bj9hmp"
HOST_JANRAIN = "https://rogers-fido.janraincapture.com"
HOST_FIDO = "https://www.fido.ca/pages/api/selfserve"
LOGIN_URL = "{}/widget/traditional_signin.jsonp".format(HOST_JANRAIN)
TOKEN_URL = "{}/widget/get_result.jsonp".format(HOST_JANRAIN)
ACCOUNT_URL = "{}/v3/login".format(HOST_FIDO)
BALANCE_URL = "{}/v2/accountOverview".format(HOST_FIDO)
FIDO_DOLLAR_URL = "{}/v1/wireless/rewards/basicinfo".format(HOST_FIDO)
USAGE_URL = "{}/v1/postpaid/dashboard/usage".format(HOST_FIDO)


DATA_MAP = {'data': ('data', 'D'),
            'text': ('text', 'BL'),
            'mms': ('text', 'M'),
            'text_int': ('text', 'SI'),
            'talk': ('talk', 'V'),
            'talk_other': ('talk', 'VL')}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Fido sensor."""
    # Create a data fetcher to support all of the configured sensors. Then make
    # the first call to init the data.

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    try:
        fido_data = FidoData(username, password)
        fido_data.update()
    except requests.exceptions.HTTPError as error:
        _LOGGER.error(error)
        return False

    name = config.get(CONF_NAME)

    sensors = []
    for variable in config[CONF_MONITORED_VARIABLES]:
        sensors.append(FidoSensor(fido_data, variable, name))

    add_devices(sensors)


class FidoSensor(Entity):
    """Implementation of a Fido sensor."""

    def __init__(self, fido_data, sensor_type, name):
        """Initialize the sensor."""
        self.client_name = name
        self.type = sensor_type
        self.entity_id = "sensor.{}_{}".format(name, sensor_type)
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self.fido_data = fido_data
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
        """Get the latest data from Fido and update the state."""
        self.fido_data.update()
        if self.type in self.fido_data.data:
            if self.fido_data.data[self.type] is not None:
                self._state = round(self.fido_data.data[self.type], 2)


class FidoData(object):
    """Get data from HydroQuebec."""

    def __init__(self, number, password):
        """Initialize the data object."""
        self.number = number
        self.password = password
        self.data = {}
        self.headers = {'User-Agent': ('Mozilla/5.0 (X11; Linux x86_64; '
                                       'rv:10.0.7) Gecko/20100101 '
                                       'Firefox/10.0.7 Iceweasel/10.0.7')}
        self.cookies = None

    def _post_login_page(self):
        """Login to Janrain."""
        # Prepare post data
        data = {
            "form": "signInForm",
            "client_id": JANRAIN_CLIENT_ID,
            "redirect_uri": "https://www.fido.ca/pages/#/",
            "response_type": "token",
            "locale": "en-US",
            "userID": self.number,
            "currentPassword": self.password,
        }
        # HTTP request
        try:
            raw_res = requests.post(LOGIN_URL, headers=self.headers,
                                    data=data, timeout=REQUESTS_TIMEOUT)
        except OSError:
            _LOGGER.error("Can not sign in")
            return False
        # Get cookies
        self.cookies = raw_res.cookies

        return True

    def _get_token(self):
        """Get token from JanRain."""
        # HTTP request
        try:
            raw_res = requests.get(TOKEN_URL,
                                   headers=self.headers,
                                   cookies=self.cookies,
                                   timeout=REQUESTS_TIMEOUT)
        except OSError:
            _LOGGER.error("Can not get token")
            return False
        # Research for json in answer
        reg_res = re.search(r"\({.*}\)", raw_res.text)
        if reg_res is None:
            _LOGGER.error("Can not finf token json")
            return False
        # Load data as json
        return_data = json.loads(reg_res.group()[1:-1])
        # Get token and uuid
        token = return_data.get('result', {}).get('accessToken')
        uuid = return_data.get('result', {}).get('userData', {}).get('uuid')
        # Check values
        if token is None or uuid is None:
            _LOGGER.error("Can not get token or uuid")
            return False
        # Update cookies
        self.cookies.update(raw_res.cookies)

        return token, uuid

    def _get_account_number(self, token, uuid):
        """Get fido account number."""
        # Data
        data = {"accessToken": token,
                "uuid": uuid}
        # Http request
        try:
            raw_res = requests.post(ACCOUNT_URL,
                                    data=data,
                                    headers=self.headers,
                                    timeout=REQUESTS_TIMEOUT)
        except OSError:
            _LOGGER.error("Can not get account number")
            return False
        # Load answer as json
        try:
            account_number = raw_res.json()\
                            .get('getCustomerAccounts', {})\
                            .get('accounts', [{}])[0]\
                            .get('accountNumber')
        except (OSError, ValueError):
            _LOGGER.error("Bad json getting account number")
            return False
        # Check collected data
        if account_number is None:
            _LOGGER.error("Can not get account number")
            return False
        # Update cookies
        self.cookies.update(raw_res.cookies)

        return account_number

    def _get_balance(self, account_number):
        """Get current balance from Fido."""
        # Prepare data
        data = {"ctn": self.number,
                "language": "en-US",
                "accountNumber": account_number}
        # Http request
        try:
            raw_res = requests.post(BALANCE_URL,
                                    data=data,
                                    headers=self.headers,
                                    cookies=self.cookies,
                                    timeout=REQUESTS_TIMEOUT)
        except OSError:
            _LOGGER.error("Can not get balance")
            return False
        # Get balance
        try:
            balance_str = raw_res.json()\
                            .get("getAccountInfo", {})\
                            .get("balance")
        except (OSError, ValueError):
            _LOGGER.error("Can not get balance as json")
            return False
        if balance_str is None:
            _LOGGER.error("Can not get balance")
            return False
        # Casting to float
        try:
            balance = float(balance_str)
        except ValueError:
            _LOGGER.error("Can not get balance as float")
            return False

        return balance

    def _get_fido_dollar(self, account_number):
        """Get current Fido dollar balance."""
        # Prepare data
        data = json.dumps({"fidoDollarBalanceFormList":
                           [{"phoneNumber": self.number,
                             "accountNumber": account_number}]})
        # Prepare headers
        headers_json = self.headers.copy()
        headers_json["Content-Type"] = "application/json;charset=UTF-8"
        # Http request
        try:
            raw_res = requests.post(FIDO_DOLLAR_URL,
                                    data=data,
                                    headers=headers_json,
                                    cookies=self.cookies,
                                    timeout=REQUESTS_TIMEOUT)
        except OSError:
            _LOGGER.error("Can not get fido dollar")
            return False
        # Get fido dollar
        try:
            fido_dollar_str = raw_res.json()\
                        .get("fidoDollarBalanceInfoList", [{}])[0]\
                        .get("fidoDollarBalance")
        except (OSError, ValueError):
            _LOGGER.error("Can not get fido dollar as json")
            return False
        if fido_dollar_str is None:
            _LOGGER.error("Can not get fido dollar")
            return False
        # Casting to float
        try:
            fido_dollar = float(fido_dollar_str)
        except ValueError:
            _LOGGER.error("Can not get fido dollar")
            return False

        return fido_dollar

    def _get_usage(self, account_number):
        """Get Fido usage.

        Get the following data
        - talk
        - text
        - data

        Roaming data is not supported yet
        """
        # Prepare data
        data = {"ctn": self.number,
                "language": "en-US",
                "accountNumber": account_number}
        # Http request
        try:
            raw_res = requests.post(USAGE_URL,
                                    data=data,
                                    headers=self.headers,
                                    cookies=self.cookies,
                                    timeout=REQUESTS_TIMEOUT)
        except OSError:
            _LOGGER.error("Can not get usage")
            return False
        # Load answer as json
        try:
            output = raw_res.json()
        except (OSError, ValueError):
            _LOGGER.error("Can not get usage as json")
            return False
        # Format data
        ret_data = {}
        for data_name, keys in DATA_MAP.items():
            key, subkey = keys
            for data in output.get(key)[0].get('wirelessUsageSummaryInfoList'):
                if data.get('usageSummaryType') == subkey:
                    # Prepare keys:
                    used_key = "{}_used".format(data_name)
                    remaining_key = "{}_remaining".format(data_name)
                    limit_key = "{}_limit".format(data_name)
                    # Get values
                    ret_data[used_key] = data.get('used', 0.0)
                    if data.get('remaining') >= 0:
                        ret_data[remaining_key] = data.get('remaining')
                    else:
                        ret_data[remaining_key] = None
                    if data.get('total') >= 0:
                        ret_data[limit_key] = data.get('total')
                    else:
                        ret_data[limit_key] = None

        return ret_data

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from HydroQuebec."""
        # Post login page
        if not self._post_login_page():
            return
        # Get token
        token_uuid = self._get_token()
        if not token_uuid:
            return
        # Get account number
        account_number = self._get_account_number(*token_uuid)
        if not token_uuid:
            return
        # Get balance
        balance = self._get_balance(account_number)
        if balance is False:
            return
        self.data['balance'] = balance
        # Get fido dollar
        fido_dollar = self._get_fido_dollar(account_number)
        if fido_dollar is False:
            return
        self.data['fido_dollar'] = fido_dollar
        # Get usage
        usage = self._get_usage(account_number)
        if not usage:
            return
        # Update data
        self.data.update(usage)
