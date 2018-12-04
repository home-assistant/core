"""
Support for the Strava API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.strava/
"""
import datetime
import logging
import os
import time

import homeassistant.helpers.config_validation as cv
import units
import voluptuous as vol
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_UNIT_SYSTEM
from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.util.json import load_json, save_json

REQUIREMENTS = ['stravalib==0.10.2']

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

ATTR_ACCESS_TOKEN = 'access_token'
ATTR_REFRESH_TOKEN = 'refresh_token'
ATTR_CLI_ID = 'client_id'
ATTR_CLI_SEC = 'client_secret'
ATTR_EXPIRES_AT = 'expires_at'

CONF_MONITORED_RESOURCES = 'monitored_resources'
CONF_ATTRIBUTION = 'Data provided by Strava.com'

DEPENDENCIES = ['http']

STRAVA_AUTH_CALLBACK_PATH = '/api/strava/callback'
STRAVA_AUTH_START = '/api/strava'
STRAVA_CONFIG_FILE = 'strava.conf'
STRAVA_DEFAULT_RESOURCES = ['activities/steps']

SCAN_INTERVAL = datetime.timedelta(minutes=1)

DEFAULT_CONFIG = {
    'client_id': 'CLIENT_ID_HERE',
    'client_secret': 'CLIENT_SECRET_HERE'
}

STRAVA_MEASUREMENTS = {
    'feet': {
        'duration': 'ms',
        'distance': 'mi',
        'elevation': 'ft',
        'height': 'in',
        'weight': 'lbs',
    },
    'meters': {
        'duration': 'milliseconds',
        'distance': 'kilometers',
        'elevation': 'meters',
        'height': 'centimeters',
        'weight': 'kilograms',
    }
}

STRAVA_RESOURCES_LIST = {

    'follower_count':
        ['Follower Count', '', 'account-arrow-left', 'athlete'],
    'friend_count':
        ['Friend Count', '', 'account-arrow-right', 'athlete'],
    'weight':
        ['Weight', 'kg', 'weight', 'athlete'],
    'max_heartrate':
        ['Maximum Heart Rate', 'BPM', 'heart-pulse', 'athlete'],
    'ftp':
        ['FTP', 'Watts', 'chart-line', 'athlete'],
    'ytd_ride_totals.distance':
        ['Year To Date Ride Distance', '', 'chart-line', 'stat'],
    'ytd_ride_totals.count':
        ['Year To Date Ride Number', '', 'chart-line', 'stat'],
    'ytd_ride_totals.elapsed_time':
        ['Year To Date Ride Elapsed Time', 's', 'chart-line', 'stat'],
    'ytd_ride_totals.elevation_gain':
        ['Year To Date Ride Elevation GAIN', '', 'chart-line', 'stat'],
    'ytd_ride_totals.moving_time':
        ['Year To Date Ride Moving Time', 's', 'chart-line', 'stat'],
    'recent_ride_totals.distance':
        ['Recent Ride Distance', '', 'chart-line', 'stat'],
    'recent_ride_totals.count':
        ['Recent Ride Number', '', 'chart-line', 'stat'],
    'recent_ride_totals.elapsed_time':
        ['Recent Ride Elapsed Time', 's', 'chart-line', 'stat'],
    'recent_ride_totals.elevation_gain':
        ['Recent Ride Elevation GAIN', '', 'chart-line', 'stat'],
    'recent_ride_totals.moving_time':
        ['Recent Ride Moving Time', 's', 'chart-line', 'stat'],
    'all_ride_totals.distance':
        ['All Ride Distance', '', 'chart-line', 'stat'],
    'all_ride_totals.count':
        ['All Ride Number', '', 'chart-line', 'stat'],
    'all_ride_totals.elapsed_time':
        ['All Ride Elapsed Time', 's', 'chart-line', 'stat'],
    'all_ride_totals.elevation_gain':
        ['All Ride Elevation GAIN', '', 'chart-line', 'stat'],
    'all_ride_totals.moving_time':
        ['All Ride Moving Time', 's', 'chart-line', 'stat'],
    'ytd_run_totals.distance':
        ['Year To Date Run Distance', '', 'chart-line', 'stat'],
    'ytd_run_totals.count':
        ['Year To Date Run Number', '', 'chart-line', 'stat'],
    'ytd_run_totals.elapsed_time':
        ['Year To Date Run Elapsed Time', 's', 'chart-line', 'stat'],
    'ytd_run_totals.elevation_gain':
        ['Year To Date Run Elevation GAIN', '', 'chart-line', 'stat'],
    'ytd_run_totals.moving_time':
        ['Year To Date Run Moving Time', 's', 'chart-line', 'stat'],
    'recent_run_totals.distance':
        ['Recent Run Distance', '', 'chart-line', 'stat'],
    'recent_run_totals.count':
        ['Recent Run Number', '', 'chart-line', 'stat'],
    'recent_run_totals.elapsed_time':
        ['Recent Run Elapsed Time', 's', 'chart-line', 'stat'],
    'recent_run_totals.elevation_gain':
        ['Recent Run Elevation GAIN', '', 'chart-line', 'stat'],
    'recent_run_totals.moving_time':
        ['Recent Run Moving Time', 's', 'chart-line', 'stat'],
    'all_run_totals.distance':
        ['All Run Distance', '', 'chart-line', 'stat'],
    'all_run_totals.count':
        ['All Run Number', '', 'chart-line', 'stat'],
    'all_run_totals.elapsed_time':
        ['All Run Elapsed Time', 's', 'chart-line', 'stat'],
    'all_run_totals.elevation_gain':
        ['All Run Elevation GAIN', '', 'chart-line', 'stat'],
    'all_run_totals.moving_time':
        ['All Run Moving Time', 's', 'chart-line', 'stat'],
    'ytd_swim_totals.distance':
        ['Year To Date Swim Distance', '', 'chart-line', 'stat'],
    'ytd_swim_totals.count':
        ['Year To Date Swim Number', '', 'chart-line', 'stat'],
    'ytd_swim_totals.elapsed_time':
        ['Year To Date Swim Elapsed Time', 's', 'chart-line', 'stat'],
    'ytd_swim_totals.elevation_gain':
        ['Year To Date Swim Elevation GAIN', '', 'chart-line', 'stat'],
    'ytd_swim_totals.moving_time':
        ['Year To Date Swim Moving Time', 's', 'chart-line', 'stat'],
    'recent_swim_totals.distance':
        ['Recent Swim Distance', '', 'chart-line', 'stat'],
    'recent_swim_totals.count':
        ['Recent Swim Number', '', 'chart-line', 'stat'],
    'recent_swim_totals.elapsed_time':
        ['Recent Swim Elapsed Time', 's', 'chart-line', 'stat'],
    'recent_swim_totals.elevation_gain':
        ['Recent Swim Elevation GAIN', '', 'chart-line', 'stat'],
    'recent_swim_totals.moving_time':
        ['Recent Swim Moving Time', 's', 'chart-line', 'stat'],
    'all_swim_totals.distance':
        ['All Swim Distance', '', 'chart-line', 'stat'],
    'all_swim_totals.count':
        ['All Swim Number', '', 'chart-line', 'stat'],
    'all_swim_totals.elapsed_time':
        ['All Swim Elapsed Time', 's', 'chart-line', 'stat'],
    'all_swim_totals.elevation_gain':
        ['All Swim Elevation GAIN', '', 'chart-line', 'stat'],
    'all_swim_totals.moving_time':
        ['All Swim Moving Time', 's', 'chart-line', 'stat'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_RESOURCES, default=STRAVA_DEFAULT_RESOURCES):
        vol.All(cv.ensure_list, [vol.In(STRAVA_RESOURCES_LIST)]),
    vol.Optional(CONF_UNIT_SYSTEM, default='default'):
        vol.In(['en_GB', 'en_US', 'metric', 'default'])
})


def request_app_setup(hass, config, add_entities, config_path,
                      discovery_info=None):
    """Assist user with configuring the Strava dev application."""
    configurator = hass.components.configurator

    def strava_configuration_callback(callback_data):
        """Handle configuration updates."""
        config_path = hass.config.path(STRAVA_CONFIG_FILE)
        if os.path.isfile(config_path):
            config_file = load_json(config_path)
            if config_file == DEFAULT_CONFIG:
                error_msg = ("You didn't correctly modify strava.conf",
                             " please try again")
                configurator.notify_errors(_CONFIGURING['strava'],
                                           error_msg)
            else:
                setup_platform(hass, config, add_entities, discovery_info)
        else:
            setup_platform(hass, config, add_entities, discovery_info)

    start_url = "{}{}".format(hass.config.api.base_url,
                              STRAVA_AUTH_CALLBACK_PATH)

    description = """Please create a Strava developer app at
                       https://strava.com/settings/api.
                       For the OAuth 2.0 Application Type choose Personal.
                       Set the Callback URL to {}.
                       They will provide you a Client ID and secret.
                       These need to be saved into the file located at: {}.
                       Then come back here and hit the below button.
                       """.format(start_url, config_path)

    submit = "I have saved my Client ID and Client Secret into strava.conf."

    _CONFIGURING['strava'] = configurator.request_config(
        'Strava', strava_configuration_callback,
        description=description, submit_caption=submit,
        description_image="/static/images/config_strava_app.png"
    )


def request_oauth_completion(hass):
    """Request user complete Strava OAuth2 flow."""
    configurator = hass.components.configurator
    if "strava" in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING['strava'], "Failed to register, please try again.")

        return

    def strava_configuration_callback(callback_data):
        """Handle configuration updates."""

    start_url = '{}{}'.format(hass.config.api.base_url, STRAVA_AUTH_START)

    description = "Please authorize Strava by visiting {}".format(start_url)

    _CONFIGURING['strava'] = configurator.request_config(
        'Strava', strava_configuration_callback,
        description=description,
        submit_caption="I have authorized Strava."
    )


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Strava sensor."""
    config_path = hass.config.path(STRAVA_CONFIG_FILE)
    if os.path.isfile(config_path):
        config_file = load_json(config_path)
        if config_file == DEFAULT_CONFIG:
            request_app_setup(
                hass, config, add_entities, config_path, discovery_info=None)
            return False
    else:
        save_json(config_path, DEFAULT_CONFIG)
        request_app_setup(
            hass, config, add_entities, config_path, discovery_info=None)
        return False

    if "strava" in _CONFIGURING:
        hass.components.configurator.request_done(_CONFIGURING.pop("strava"))

    from stravalib.client import Client

    access_token = config_file.get(ATTR_ACCESS_TOKEN)
    refresh_token = config_file.get(ATTR_REFRESH_TOKEN)
    expires_at = config_file.get(ATTR_EXPIRES_AT)
    if None not in (access_token, refresh_token):
        strava_client = Client()
        strava_client.access_token = access_token
        strava_client.refresh_token = refresh_token
        strava_client.token_expires_at = expires_at

        # tokens last 6 hours
        if int(time.time()) > expires_at:
            strava_client.refresh_access_token(config_file.get(ATTR_CLI_ID),
                                               config_file.get(ATTR_CLI_SEC),
                                               refresh_token)
        dev = []
        for resource in config.get(CONF_MONITORED_RESOURCES):

            dev.append(StravaSensor(
                strava_client, config_path, resource,
                hass.config.units.is_metric))
        add_entities(dev, True)

    else:
        strava_client = Client()
        strava_auth_start_url = strava_client.authorization_url(
            client_id=config_file.get(ATTR_CLI_ID),
            redirect_uri='{}{}'.format(
                hass.config.api.base_url,
                STRAVA_AUTH_CALLBACK_PATH
            ),
            scope=['profile:read_all']
        )

        hass.http.register_redirect(STRAVA_AUTH_START, strava_auth_start_url)
        hass.http.register_view(StravaAuthCallbackView(
            config, add_entities, strava_client, config_file))

        request_oauth_completion(hass)


class StravaAuthCallbackView(HomeAssistantView):
    """Handle OAuth finish callback requests."""

    requires_auth = False
    url = STRAVA_AUTH_CALLBACK_PATH
    name = 'api:strava:callback'

    def __init__(self, config, add_entities, strava_client, config_file):
        """Initialize the OAuth callback view."""
        self.config = config
        self.add_entities = add_entities
        self.strava_client = strava_client
        self.config_file = config_file

    @callback
    def get(self, request):
        """Finish OAuth callback request."""

        hass = request.app['hass']
        data = request.query

        response_message = """Strava has been successfully authorized!
        You can close this window now!"""

        result = None
        if data.get('code') is not None:
            result = self.strava_client.exchange_code_for_token(
                self.config_file.get(ATTR_CLI_ID),
                self.config_file.get(ATTR_CLI_SEC),
                data.get('code')
            )
        else:
            _LOGGER.error("Unknown error when authing")
            response_message = """Something went wrong when
                attempting authenticating with Strava.
                An unknown error occurred. Please try again!
                """

        if result is None:
            _LOGGER.error("Unknown error when authing")
            response_message = """Something went wrong when
                attempting authenticating with Strava.
                An unknown error occurred. Please try again!
                """

        html_response = """<html><head><title>Strava Auth</title></head>
        <body><h1>{}</h1></body></html>""".format(response_message)

        if result:
            config_contents = {
                ATTR_ACCESS_TOKEN: result.get('access_token'),
                ATTR_REFRESH_TOKEN: result.get('refresh_token'),
                ATTR_EXPIRES_AT: result.get('expires_at'),
                ATTR_CLI_ID: self.config_file.get(ATTR_CLI_ID),
                ATTR_CLI_SEC: self.config_file.get(ATTR_CLI_SEC)
            }
        save_json(hass.config.path(STRAVA_CONFIG_FILE), config_contents)

        hass.async_add_job(setup_platform, hass, self.config,
                           self.add_entities)

        return html_response


class StravaSensor(Entity):
    """Implementation of a Strava sensor."""

    def __init__(self, strava_client, config_path, resource_type,
                 is_metric, extra=None):
        """Initialize the Strava sensor."""
        self.strava_client = strava_client
        self.config_path = config_path
        self.resource_type = resource_type
        self.is_metric = is_metric
        self.extra = extra
        self._name = STRAVA_RESOURCES_LIST[self.resource_type][0]
        unit_type = STRAVA_RESOURCES_LIST[self.resource_type][1]
        self._unit_of_measurement = unit_type
        self._state = 0

    @property
    def name(self):
        """Return the name of the sensor."""
        return ' '.join(['Strava', self._name])

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return 'mdi:{}'.format(STRAVA_RESOURCES_LIST[self.resource_type][2])

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION

        if self.extra:
            attrs['model'] = self.extra.get('deviceVersion')
            attrs['type'] = self.extra.get('type').lower()

        return attrs

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data from the Strava API and update the states."""
        if STRAVA_RESOURCES_LIST[self.resource_type][3] == 'stat':
            response = self.strava_client.get_athlete_stats()
            if '.' in self.resource_type:
                parts = self.resource_type.split('.')
                field = getattr(response, parts[0])
                temp_state = getattr(field, parts[1])
            else:
                temp_state = getattr(response, self.resource_type)
        else:
            response = self.strava_client.get_athlete()
            temp_state = getattr(response, self.resource_type)
        if type(temp_state) == units.quantity.Quantity:
            self._state = temp_state.get_num()
        else:
            self._state = temp_state
