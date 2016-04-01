"""
Support for the Fitbit API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.fitbit/
"""
import os
import json
import logging
import datetime
import time

from homeassistant.const import HTTP_OK
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity
from homeassistant.loader import get_component

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['fitbit==0.2.2']
DEPENDENCIES = ['http']

ICON = 'mdi:walk'

_CONFIGURING = {}

# Return cached results if last scan was less then this time ago.
MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=30)

FITBIT_AUTH_START = '/auth/fitbit'
FITBIT_AUTH_CALLBACK_PATH = '/auth/fitbit/callback'

FITBIT_CONFIG_FILE = 'fitbit.conf'

FITBIT_RESOURCES_LIST = {
    "activities/activityCalories": "cal",
    "activities/calories": "cal",
    "activities/caloriesBMR": "cal",
    "activities/distance": "",
    "activities/elevation": "",
    "activities/floors": "floors",
    "activities/heart": "bpm",
    "activities/minutesFairlyActive": "minutes",
    "activities/minutesLightlyActive": "minutes",
    "activities/minutesSedentary": "minutes",
    "activities/minutesVeryActive": "minutes",
    "activities/steps": "steps",
    "activities/tracker/activityCalories": "cal",
    "activities/tracker/calories": "cal",
    "activities/tracker/distance": "",
    "activities/tracker/elevation": "",
    "activities/tracker/floors": "floors",
    "activities/tracker/minutesFairlyActive": "minutes",
    "activities/tracker/minutesLightlyActive": "minutes",
    "activities/tracker/minutesSedentary": "minutes",
    "activities/tracker/minutesVeryActive": "minutes",
    "activities/tracker/steps": "steps",
    "body/bmi": "BMI",
    "body/fat": "%",
    "sleep/awakeningsCount": "times awaken",
    "sleep/efficiency": "%",
    "sleep/minutesAfterWakeup": "minutes",
    "sleep/minutesAsleep": "minutes",
    "sleep/minutesAwake": "minutes",
    "sleep/minutesToFallAsleep": "minutes",
    "sleep/startTime": "start time",
    "sleep/timeInBed": "time in bed",
    "body/weight": ""
}

FITBIT_DEFAULT_RESOURCE_LIST = ["activities/steps"]

FITBIT_MEASUREMENTS = {
    "en_US": {
        "duration": "ms",
        "distance": "mi",
        "elevation": "ft",
        "height": "in",
        "weight": "lbs",
        "body": "in",
        "liquids": "fl. oz.",
        "blood glucose": "mg/dL",
    },
    "en_UK": {
        "duration": "milliseconds",
        "distance": "kilometers",
        "elevation": "meters",
        "height": "centimeters",
        "weight": "stone",
        "body": "centimeters",
        "liquids": "millileters",
        "blood glucose": "mmol/l"
    },
    "metric": {
        "duration": "milliseconds",
        "distance": "kilometers",
        "elevation": "meters",
        "height": "centimeters",
        "weight": "kilograms",
        "body": "centimeters",
        "liquids": "millileters",
        "blood glucose": "mmol/l"
    }
}


def config_from_file(filename, config=None):
    """Small configuration file management function."""
    if config:
        # We're writing configuration
        try:
            with open(filename, 'w') as fdesc:
                fdesc.write(json.dumps(config))
        except IOError as error:
            _LOGGER.error('Saving config file failed: %s', error)
            return False
        return config
    else:
        # We're reading config
        if os.path.isfile(filename):
            try:
                with open(filename, 'r') as fdesc:
                    return json.loads(fdesc.read())
            except IOError as error:
                _LOGGER.error('Reading config file failed: %s', error)
                # This won't work yet
                return False
        else:
            return {}


def request_configuration(hass):
    """Request configuration steps from the user."""
    configurator = get_component('configurator')
    if 'fitbit' in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING['fitbit'], "Failed to register, please try again.")

        return

    # pylint: disable=unused-argument
    def fitbit_configuration_callback(callback_data):
        """The actions to do when our configuration callback is called."""
        print("Configured!")
        # setup_fitbit(hass, network, config)

    _CONFIGURING['fitbit'] = configurator.request_config(
        hass, "Fitbit", fitbit_configuration_callback,
        description=('Please authorize Fitbit by visiting '
                     'http://localhost:8123/auth/fitbit'),
        submit_caption="I have authorized Fitbit."
    )

# pylint: disable=too-many-locals


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Fitbit sensor."""
    if None in (config.get('client_id'), config.get('client_secret')):
        _LOGGER.error(
            "You must set client_id and client_secret to use Fitbit!")
        return False

    if 'fitbit' in _CONFIGURING:
        get_component('configurator').request_done(_CONFIGURING.pop('fitbit'))

    config_path = hass.config.path(FITBIT_CONFIG_FILE)
    if os.path.isfile(config_path):
        config_file = config_from_file(config_path)
    else:
        default_config = {'client_id': config.get('client_id'),
                          'client_secret': config.get('client_secret')}
        config_file = config_from_file(config_path, default_config)

    import fitbit

    access_token = config_file.get('access_token')
    refresh_token = config_file.get('refresh_token')
    if None not in (access_token, refresh_token):
        authd_client = fitbit.Fitbit(config.get('client_id'),
                                     config.get('client_secret'),
                                     access_token=access_token,
                                     refresh_token=refresh_token)

        if int(time.time()) - config_file.get('last_saved_at', 0) > 3600:
            authd_client.client.refresh_token()

        authd_client.system = authd_client.user_profile_get()['user']['locale']

        dev = []
        for resource in config.get('monitored_resources',
                                   FITBIT_DEFAULT_RESOURCE_LIST):
            dev.append(FitbitSensor(authd_client, config_path, resource))
        add_devices(dev)

    else:
        oauth = fitbit.api.FitbitOauth2Client(config.get('client_id'),
                                              config.get('client_secret'))
        redirect_uri = "http://127.0.0.1:8123/auth/fitbit/callback"

        def _start_fitbit_auth(handler, path_match, data):
            """Start Fitbit OAuth2 flow."""
            url, _ = oauth.authorize_token_url(redirect_uri=redirect_uri,
                                               scope=["activity", "heartrate",
                                                      "nutrition", "profile",
                                                      "settings", "sleep",
                                                      "weight"])
            handler.send_response(301)
            handler.send_header('Location', url)
            handler.end_headers()

        def _finish_fitbit_auth(handler, path_match, data):
            """Finish Fitbit OAuth2 flow."""
            success_html = b"""<html><head><title>Fitbit Auth</title></head>
            <body><h1>Fitbit has been successfully authorized! You can close
            this window now!</h1></body></html>"""
            handler.send_response(HTTP_OK)
            handler.send_header("Content-type", "text/html")
            handler.end_headers()
            handler.wfile.write(success_html)
            from oauthlib.oauth2.rfc6749.errors import MismatchingStateError
            from oauthlib.oauth2.rfc6749.errors import MissingTokenError
            if data.get('code') is not None:
                try:
                    oauth.fetch_access_token(data.get('code'), redirect_uri)
                except MissingTokenError as error:
                    _LOGGER.error("Missing token: %s", error)
                except MismatchingStateError as error:
                    _LOGGER.error("Mismatched state, CSRF error: %s", error)
            else:
                _LOGGER.error("Unknown error when authing")

            config_contents = {
                'access_token': oauth.token['access_token'],
                'refresh_token': oauth.token['refresh_token'],
                'client_id': oauth.client_id,
                'client_secret': oauth.client_secret
            }
            if not config_from_file(config_path, config_contents):
                _LOGGER.error('failed to save config file')

            setup_platform(hass, config, add_devices, discovery_info=None)

        hass.http.register_path('GET', FITBIT_AUTH_START, _start_fitbit_auth)
        hass.http.register_path('GET', FITBIT_AUTH_CALLBACK_PATH,
                                _finish_fitbit_auth)

        request_configuration(hass)


# pylint: disable=too-few-public-methods
class FitbitSensor(Entity):
    """Implementation of a Fitbit sensor."""

    def __init__(self, client, config_path, resource_type):
        """Initialize the Uber sensor."""
        self.client = client
        self.config_path = config_path
        self.resource_type = resource_type
        pretty_resource = self.resource_type.replace("activities/", "")
        pretty_resource = pretty_resource.replace("/", " ")
        pretty_resource = pretty_resource.title()
        if pretty_resource == "Body Bmi":
            pretty_resource = "BMI"
        self._name = pretty_resource
        unit_type = FITBIT_RESOURCES_LIST[self.resource_type]
        if unit_type == "":
            split_resource = self.resource_type.split("/")
            measurement_system = FITBIT_MEASUREMENTS[self.client.system]
            unit_type = measurement_system[split_resource[-1]]
        self._unit_of_measurement = unit_type
        self._state = 0
        self.update()

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
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    # pylint: disable=too-many-branches
    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from the Fitbit API and update the states."""
        container = self.resource_type.replace("/", "-")
        response = self.client.time_series(self.resource_type, period='7d')
        self._state = response[container][-1].get('value')
        if self.resource_type == "activities/heart":
            self._state = response[container][-1].get('restingHeartRate')
        config_contents = {
            'access_token': self.client.client.token['access_token'],
            'refresh_token': self.client.client.token['refresh_token'],
            'client_id': self.client.client.client_id,
            'client_secret': self.client.client.client_secret,
            'last_saved_at': int(time.time())
        }
        if not config_from_file(self.config_path, config_contents):
            _LOGGER.error('failed to save config file')
