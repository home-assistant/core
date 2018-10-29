"""
Support for EnerTalk Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.enertalk/
"""
from datetime import datetime, timedelta
import logging
import requests
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_MONITORED_CONDITIONS)
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.util.json import load_json, save_json

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

ATTR_ACCESS_TOKEN = 'access_token'
ATTR_REFRESH_TOKEN = 'refresh_token'

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_REAL_TIME_INTERVAL = 'real_time_interval'
CONF_BILLING_INTERVAL = 'billing_interval'

ENERTALK_AUTH_CALLBACK_PATH = '/api/enertalk/callback'
ENERTALK_CONFIG_FILE = 'enertalk.conf'

DEFAULT_NAME = 'EnerTalk'

DEPENDENCIES = ['http']
SCAN_INTERVAL = timedelta(seconds=10)

_REAL_TIME_MON_COND = {
    'real_time_usage': ['Real Time', 'Usage', 'W', 'mdi:pulse']
}
_BILLING_MON_COND = {
    'today_usage': ['Today', 'Usage', 'kWh', 'mdi:trending-up'],
    'today_charge': ['Today', 'Charge', 'Won', 'mdi:currency-krw'],
    'yesterday_usage': ['Yesterday', 'Usage', 'kWh', 'mdi:trending-up'],
    'yesterday_charge': ['Yesterday', 'Charge', 'Won', 'mdi:currency-krw'],
    'month_usage': ['Month', 'Usage', 'kWh', 'mdi:trending-up'],
    'month_charge': ['Month', 'Charge', 'Won', 'mdi:currency-krw'],
    'estimate_usage': ['Estimate', 'Usage', 'kWh', 'mdi:calendar-question'],
    'estimate_charge': ['Estimate', 'Charge', 'Won', 'mdi:currency-krw']
}
_MONITORED_CONDITIONS = list(_REAL_TIME_MON_COND.keys()) + \
                        list(_BILLING_MON_COND.keys())

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_CLIENT_ID): cv.string,
    vol.Required(CONF_CLIENT_SECRET): cv.string,
    vol.Optional(CONF_REAL_TIME_INTERVAL, default=timedelta(seconds=10)):
        vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_BILLING_INTERVAL, default=timedelta(seconds=1800)):
        vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(_MONITORED_CONDITIONS)]),
})


def request_oauth_completion(hass, config, add_entities, oauth_url):
    """Request user complete Enertalk OAuth2 flow."""
    configurator = hass.components.configurator
    if DEFAULT_NAME in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[DEFAULT_NAME],
            "Failed to register, please try again.")
        return

    def enertalk_configuration_callback(callback_data):
        """Handle configuration updates."""
        setup_platform(hass, config, add_entities)

    description = 'Please authorize EnerTalk by visiting {}'.format(oauth_url)
    _CONFIGURING[DEFAULT_NAME] = configurator.request_config(
        DEFAULT_NAME, enertalk_configuration_callback,
        description=description,
        link_name='{} Sign in'.format(DEFAULT_NAME),
        link_url=oauth_url
    )


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a EnerTalk Sensors."""
    from pytz import timezone

    name = config.get(CONF_NAME)
    client_id = config.get(CONF_CLIENT_ID)
    client_secret = config.get(CONF_CLIENT_SECRET)
    real_time_interval = config.get(CONF_REAL_TIME_INTERVAL)
    billing_interval = config.get(CONF_BILLING_INTERVAL)
    monitored_conditions = config.get(CONF_MONITORED_CONDITIONS)

    client = EnerTalkOauth2Client(client_id,
                                  client_secret,
                                  hass.config.path(ENERTALK_CONFIG_FILE))
    try:
        client.load_token()
        device = client.get('sites')[0]
        device['timezone'] = timezone(device['timezone'])

        if DEFAULT_NAME in _CONFIGURING:
            hass.components.configurator\
                .request_done(_CONFIGURING.pop(DEFAULT_NAME))

        sensors = []

        for variable in monitored_conditions:
            if variable in _REAL_TIME_MON_COND:
                sensors += [EnerTalkRealTimeSensor(
                    name, device, variable, _REAL_TIME_MON_COND[variable],
                    client, real_time_interval)]

        billing_api = {}
        for variable in monitored_conditions:
            if variable in _BILLING_MON_COND:
                billing_type = _BILLING_MON_COND[variable][0]
                if billing_type not in billing_api:
                    billing_api[billing_type] = EnerBillingApi(
                        client, device, billing_type, billing_interval)
                sensors += [EnerTalkBillingSensor(
                    name, device, variable,
                    _BILLING_MON_COND[variable], billing_api[billing_type])]

        add_entities(sensors, True)

    except PlatformNotReady:
        redirect_url = '{}{}'.format(
            hass.config.api.base_url, ENERTALK_AUTH_CALLBACK_PATH)
        oauth_url = client.authorize_token_url(redirect_url)
        hass.http.register_view(EnerTalkAuthCallbackView(
            config, add_entities, client))
        request_oauth_completion(hass, config, add_entities, oauth_url)


class EnerTalkAuthCallbackView(HomeAssistantView):
    """Handle OAuth finish callback requests."""

    url = ENERTALK_AUTH_CALLBACK_PATH
    name = 'api:enertalk:callback'
    requires_auth = False

    def __init__(self, config, add_entities, client):
        """Initialize the OAuth callback view."""
        self.config = config
        self.add_entities = add_entities
        self.client = client

    @callback
    def get(self, request):
        """Finish OAuth callback request."""
        from aiohttp import web
        hass = request.app['hass']
        data = request.query

        response_message = 'Enertalk has been successfully authorized! ' \
                           'You can close this window now!'
        html_response = '<html><head><title>EnerTalk Auth</title></head>' \
                        '<body><h1>{}</h1></body></html>'

        if data.get('code') is not None:
            self.client.fetch_access_token(data.get('code'))
            hass.async_add_job(setup_platform, hass, self.config,
                               self.add_entities)
        else:
            _LOGGER.error('Unknown error when authing')
            response_message = 'Something went wrong when' \
                               'attempting authenticating with Enertalk.' \
                               'An unknown error occurred. Please try again!'

        html_response = html_response.format(response_message)
        return web.Response(text=html_response.format(html_response),
                            content_type='text/html')


class EnerTalkOauth2Client:
    """EnerTalk OAuth 2 Client."""

    AUTHORIZE_ENDPOINT = 'https://auth.enertalk.com'
    API_ENDPOINT = 'https://api2.enertalk.com'

    def __init__(self, client_id, client_secret, config_path):
        """Initialize the OAuth 2 Client."""
        self.client_id = client_id
        self.client_secret = client_secret
        self.config_path = config_path
        self.token = {}

    def load_token(self):
        """Load the stored token."""
        import os
        if not os.path.isfile(self.config_path):
            raise PlatformNotReady

        self.token = load_json(self.config_path)

    def authorize_token_url(self, redirect_url):
        """Authorize code grant type of OAuth 2.0 URL."""
        return '{}/authorization' \
               '?response_type=code&client_id={}&redirect_uri={}'\
            .format(self.AUTHORIZE_ENDPOINT, self.client_id, redirect_url)

    def fetch_access_token(self, code):
        """Fetch Access Token."""
        payload = {'grant_type': 'authorization_code',
                   'client_id': self.client_id,
                   'client_secret': self.client_secret,
                   'code': code}
        self.fetch_token({}, payload)

    def renew_refresh_token(self):
        """Renew Refresh Token."""
        import base64
        basic_auth = base64.standard_b64encode(
            '{}:{}'.format(self.client_id, self.client_secret).encode('utf-8'))
        basic_auth = basic_auth.decode('utf-8')
        headers = {'Authorization': 'Basic {}'.format(basic_auth)}
        payload = {'grant_type': 'refresh_token',
                   'refresh_token': self.token[ATTR_REFRESH_TOKEN]}
        self.fetch_token(headers, payload)

    def fetch_token(self, add_headers, payload):
        """Token is imported through the OAuth 2.0 API."""
        headers = {'Content-Type': 'application/json'}
        headers.update(add_headers)
        try:
            response = requests.post(
                '{}/token'.format(self.AUTHORIZE_ENDPOINT),
                headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            _LOGGER.debug('JSON Response: %s', response.json())
            self.token = response.json()
            save_json(self.config_path, self.token)
        except Exception as ex:
            _LOGGER.error(
                'Failed to update EnerToken status from token. Error: %s',
                ex)
            raise

    def request(self, url):
        """Enertalk API request."""
        headers = {'Authorization': 'Bearer {}'.format(
            self.token[ATTR_ACCESS_TOKEN]), 'accept-version': '2.0.0'}
        try:
            response = requests.get(
                '{}/{}'.format(self.API_ENDPOINT, url),
                headers=headers, timeout=10)
            _LOGGER.debug('JSON Response: %s', response.content.decode('utf8'))
            return response
        except Exception as ex:
            _LOGGER.error('Failed to update EnerToken status Error: %s', ex)
            raise

    def get(self, url):
        """Get the EnerTalk data."""
        response = self.request(url)
        if response.status_code == 401:
            error_type = response.json()['type']
            if error_type == 'UnauthorizedError':
                self.renew_refresh_token()
                response = self.request(url)
        return response.json()


class EnerTalkSensor(Entity):
    """Representation of a EnerTalk Sensor."""

    def __init__(self, name, device, variable, variable_info):
        """Initialize the EnerTalk sensor."""
        self._name = name
        self._device = device
        self.var_id = variable
        self.var_period = variable_info[0]
        self.var_type = variable_info[1]
        self.var_units = variable_info[2]
        self.var_icon = variable_info[3]

    @property
    def entity_id(self):
        """Return the entity ID."""
        return 'sensor.{}_{}'.format(self._name, self.var_id)

    @property
    def name(self):
        """Return the name of the sensor, if any."""
        return '{} {}'.format(self.var_period, self.var_type)

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self.var_icon

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self.var_units

    @property
    def device_info(self):
        """Return information about the device."""
        return {
            'id': self._device['id'],
            'name': self._device['name'],
            'country': self._device['country'],
            'timezone': self._device['timezone'],
            'description': self._device['description']
        }


class EnerBillingApi:
    """Class to interface with EnerTalk Billing API."""

    def __init__(self, client, device, billing_type, interval):
        """Initialize the Billing API wrapper class."""
        self.client = client
        self.site_id = device['id']
        self.timezone = device['timezone']
        self.type = billing_type
        self.result = {}
        self.update = Throttle(interval)(self._update)

    def _update(self):
        """Update function for updating api information."""
        param = ''
        today_date = datetime.now(tz=self.timezone) \
            .replace(hour=0, minute=0, second=0, microsecond=0)
        if self.type == 'Today':
            param = '?period=day&start={}'.format(
                today_date.timestamp() * 1000)
        elif self.type == 'Yesterday':
            param = '?period=day&start={}&end={}'.format(
                (today_date - timedelta(1)).timestamp() * 1000,
                today_date.timestamp() * 1000)
        elif self.type == 'Estimate':
            param = '?timeType=pastToFuture'

        self.result = self.client.get(
            'sites/{}/usages/billing{}'.format(self.site_id, param))
        self.result['charge'] = self.result['bill']['usage']['charge']


class EnerTalkRealTimeSensor(EnerTalkSensor):
    """Representation of a EnerTalk RealTime Sensor."""

    def __init__(self, name, device, variable, variable_info, client,
                 interval):
        """Initialize the Real Time Sensor."""
        super().__init__(name, device, variable, variable_info)
        self.site_id = self._device['id']
        self.client = client
        self.result = {}
        self.update = Throttle(interval)(self._update)

    @property
    def state(self):
        """Return the state of the sensor."""
        return round(self.result['activePower'] * 0.001, 2)

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {
            'time': datetime.fromtimestamp(
                self.result['timestamp'] / 1000,
                self._device['timezone']).strftime('%Y-%m-%d %H:%M:%S'),
            'current': self.result['current'],
            'active_power': self.result['activePower'],
            'billing_active_power': self.result['billingActivePower'],
            'apparent_power': self.result['apparentPower'],
            'reactive_power': self.result['reactivePower'],
            'power_factor': self.result['powerFactor'],
            'voltage': self.result['voltage'],
            'positive_energy': self.result['positiveEnergy'],
            'negative_energy': self.result['negativeEnergy'],
            'positive_energy_reactive': self.result['positiveEnergyReactive'],
            'negative_energy_reactive': self.result['negativeEnergyReactive']
        }

    def _update(self):
        """Update function for updating api information."""
        if self.client is not None:
            self.result = self.client.get(
                'sites/{}/usages/realtime'.format(self.site_id))


class EnerTalkBillingSensor(EnerTalkSensor):
    """Representation of a EnerTalk Billing Sensor."""

    def __init__(self, name, device, variable, variable_info, api):
        """Initialize the Billing Sensor."""
        super().__init__(name, device, variable, variable_info)
        self.api = api

    @property
    def state(self):
        """Return the state of the sensor."""
        if self.var_type == 'Usage':
            return round(self.api.result['usage'] * 0.000001, 2)
        return round(self.api.result['charge'], 1)

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {
            'period': self.api.result['period'],
            'start': datetime.fromtimestamp(
                self.api.result['start'] / 1000,
                self._device['timezone']).strftime('%Y-%m-%d %H:%M:%S'),
            'end':  datetime.fromtimestamp(
                self.api.result['end'] / 1000,
                self._device['timezone']).strftime('%Y-%m-%d %H:%M:%S')
        }

    def update(self):
        """Get the latest state of the sensor."""
        if self.api is not None:
            self.api.update()
