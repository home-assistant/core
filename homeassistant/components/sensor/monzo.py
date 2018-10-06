"""
Support for the Monzo API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.monzo/
"""
import os
import logging
import datetime
import time

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.const import ATTR_ID
from homeassistant.const import CONF_ID
from homeassistant.helpers.entity import Entity
#from homeassistant.helpers.icon import icon_for_battery_level
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json, save_json


REQUIREMENTS = ['monzotomtest==0.6.1']

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

ATTR_ACCESS_TOKEN = 'access_token'
ATTR_REFRESH_TOKEN = 'refresh_token'
ATTR_CLIENT_ID = 'client_id'
ATTR_CLIENT_SECRET = 'client_secret'
ATTR_LAST_SAVED_AT = 'last_saved_at'

CONF_MONITORED_RESOURCES = 'monitored_resources'
CONF_ATTRIBUTION = 'Data provided by Monzo.com'

DEPENDENCIES = ['http']

MONZO_AUTH_CALLBACK_PATH = '/api/monzo/callback'
MONZO_AUTH_START = '/api/monzo'
MONZO_CONFIG_FILE = 'monzo.conf'
MONZO_DEFAULT_RESOURCES = ['balance']

SCAN_INTERVAL = datetime.timedelta(minutes=30)

DEFAULT_CONFIG = {
    'client_id': 'CLIENT_ID_HERE',
    'client_secret': 'CLIENT_SECRET_HERE'
}

MONZO_RESOURCES_LIST = {
    'balance': ['Account Balance', 'GBP', 'cash'],
    'dailyspend': ['Spent Today', 'GBP', 'cash']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MONITORED_RESOURCES, default=MONZO_DEFAULT_RESOURCES):
        vol.All(cv.ensure_list, [vol.In(MONZO_RESOURCES_LIST)]),
    vol.Optional(CONF_ID, default=""): cv.string
})


def request_app_setup(hass, config, add_entities, config_path,
                      discovery_info=None):
    """Assist user with configuring the Monzo dev application."""
    configurator = hass.components.configurator

    def monzo_configuration_callback(callback_data):
        """Handle configuration updates."""
        config_path = hass.config.path(MONZO_CONFIG_FILE)
        if os.path.isfile(config_path):
            config_file = load_json(config_path)
            if config_file == DEFAULT_CONFIG:
                error_msg = ("You didn't correctly modify monzo.conf",
                             " please try again")
                configurator.notify_errors(_CONFIGURING['monzo'],
                                           error_msg)
            else:
                setup_platform(hass, config, add_entities, discovery_info)
        else:
            setup_platform(hass, config, add_entities, discovery_info)

    start_url = "{}{}".format(hass.config.api.base_url,
                              MONZO_AUTH_CALLBACK_PATH)

    description = """Please create a Monzo Client at
                       https://developers.monzo.com/.
                       For the OAuth 2.0 Application Type choose Confidential.
                       Set the Redirect URL to {}.
                       They will provide you a Client ID and secret.
                       These need to be saved into the file located at: {}.
                       Then come back here and hit the below button.
                       """.format(start_url, config_path)

    submit = "I have saved my Client ID and Client Secret into monzo.conf."

    _CONFIGURING['monzo'] = configurator.request_config(
        'Monzo', monzo_configuration_callback,
        description=description, submit_caption=submit,
        description_image="/static/images/config_fitbit_app.png"
    )


def request_oauth_completion(hass):
    """Request user complete Monzo OAuth2 flow."""
    configurator = hass.components.configurator
    if "monzo" in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING['monzo'], "Failed to register, please try again.")

        return

    def monzo_configuration_callback(callback_data):
        """Handle configuration updates."""

    start_url = '{}{}'.format(hass.config.api.base_url, MONZO_AUTH_START)

    description = "Please authorize Monzo by visiting {}".format(start_url)

    _CONFIGURING['monzo'] = configurator.request_config(
        'Monzo', monzo_configuration_callback,
        description=description,
        submit_caption="I have authorized Monzo."
    )


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Monzo sensor."""
    config_path = hass.config.path(MONZO_CONFIG_FILE)
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

    if "monzo" in _CONFIGURING:
        hass.components.configurator.request_done(_CONFIGURING.pop("monzo"))

    import monzo

    access_token = config_file.get(ATTR_ACCESS_TOKEN)
    refresh_token = config_file.get(ATTR_REFRESH_TOKEN)
    expires_at = config_file.get(ATTR_LAST_SAVED_AT)
    if None not in (access_token, refresh_token):
        # Load existing OAuth session
        authd_client = monzo.MonzoOAuth2Client(client_id = config_file.get(ATTR_CLIENT_ID),
                                     client_secret = config_file.get(ATTR_CLIENT_SECRET),
                                     access_token=access_token,
                                     refresh_token=refresh_token,
                                     expires_at=expires_at,
                                     refresh_cb=lambda x: None)

        if int(time.time()) - expires_at > 3600:
            authd_client.client.refresh_token()

        client = monzo.Monzo.from_oauth_session(authd_client)
        account_id = config.get(CONF_ID)

        #Create sensors to be added to hass
        dev = []
        print("making a sensor")
        for resource in config.get(CONF_MONITORED_RESOURCES):
                dev.append(MonzoSensor(client, config_path, resource, account_id))

        add_entities(dev, True)

    else:
        # No existing OAuth session
        # Need to authenticate
        print("trying to reauth")
        redirect_uri = '{}{}'.format(hass.config.api.base_url,
                                     MONZO_AUTH_CALLBACK_PATH)

        oauth = monzo.MonzoOAuth2Client(
            client_id = config_file.get(ATTR_CLIENT_ID),
            client_secret = config_file.get(ATTR_CLIENT_SECRET),
            redirect_uri = redirect_uri)

        monzo_auth_start_url, _ = oauth.authorize_token_url()

        hass.http.register_redirect(MONZO_AUTH_START, monzo_auth_start_url)
        hass.http.register_view(MonzoAuthCallbackView(
            config, add_entities, oauth))

        request_oauth_completion(hass)


class MonzoAuthCallbackView(HomeAssistantView):
    """Handle OAuth finish callback requests."""

    requires_auth = False
    url = MONZO_AUTH_CALLBACK_PATH
    name = 'api:monzo:callback'

    def __init__(self, config, add_entities, oauth):
        """Initialize the OAuth callback view."""
        self.config = config
        self.add_entities = add_entities
        self.oauth = oauth

    @callback
    def get(self, request):
        """Finish OAuth callback request."""
        from oauthlib.oauth2.rfc6749.errors import MismatchingStateError
        from oauthlib.oauth2.rfc6749.errors import MissingTokenError

        hass = request.app['hass']
        data = request.query

        response_message = """Monzo has been successfully authorized!
        You can close this window now!"""

        result = None
        if data.get('code') is not None:
            redirect_uri = '{}{}'.format(
                hass.config.api.base_url, MONZO_AUTH_CALLBACK_PATH)

            try:
                result = self.oauth.fetch_access_token(data.get('code'),
                                                       redirect_uri)
            except MissingTokenError as error:
                _LOGGER.error("Missing token: %s", error)
                response_message = """Something went wrong when
                attempting authenticating with Monzo. The error
                encountered was {}. Please try again!""".format(error)
            except MismatchingStateError as error:
                _LOGGER.error("Mismatched state, CSRF error: %s", error)
                response_message = """Something went wrong when
                attempting authenticating with Monzo. The error
                encountered was {}. Please try again!""".format(error)
        else:
            _LOGGER.error("Unknown error when authing")
            response_message = """Something went wrong when
                attempting authenticating with Monzo.
                An unknown error occurred. Please try again!
                """

        if result is None:
            _LOGGER.error("Unknown error when authing")
            response_message = """Something went wrong when
                attempting authenticating with Monzo.
                An unknown error occurred. Please try again!
                """

        html_response = """<html><head><title>Monzo Auth</title></head>
        <body><h1>{}</h1></body></html>""".format(response_message)

        if result:
            config_contents = {
                ATTR_ACCESS_TOKEN: result.get('access_token'),
                ATTR_REFRESH_TOKEN: result.get('refresh_token'),
                ATTR_CLIENT_ID: self.oauth.client_id,
                ATTR_CLIENT_SECRET: self.oauth.client_secret,
                ATTR_LAST_SAVED_AT: int(time.time())
            }
        save_json(hass.config.path(MONZO_CONFIG_FILE), config_contents)

        hass.async_add_job(setup_platform, hass, self.config,
                           self.add_entities)

        return html_response


class MonzoSensor(Entity):
    """Implementation of a Monzo sensor."""

    def __init__(self, client, config_path, resource_type, account_id,extra=None):
        """Initialize the Monzo sensor."""
        self.client = client
        self.config_path = config_path
        self.resource_type = resource_type
        self.extra = extra
        self._name = 'Monzo Balance'
        print("made a sensor")
        self._name = MONZO_RESOURCES_LIST[self.resource_type][0]
        self._unit_of_measurement = MONZO_RESOURCES_LIST[self.resource_type][1]
        self._state = 0

        if account_id == "":
            self._account_id = self.client.get_first_account()['id']
        else:
            self._account_id = account_id

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
        return 'mdi:{}'.format(MONZO_RESOURCES_LIST[self.resource_type][2])

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        attrs[ATTR_ID] = self._account_id
        attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION

        return attrs

    def update(self):
        """Get the latest data from the Monzo API and update the states."""

        if self.resource_type == 'balance':
            self._state = self.client.get_balance(self._account_id)['balance'] / 100
        elif self.resource_type == 'dailyspend':
            self._state = self.client.get_balance(self._account_id)['spend_today'] / 100

        token = self.client.oauth_session.session.token
        config_contents = {
            ATTR_ACCESS_TOKEN: token.get('access_token'),
            ATTR_REFRESH_TOKEN: token.get('refresh_token'),
            ATTR_CLIENT_ID: self.client.oauth_session.client_id,
            ATTR_CLIENT_SECRET: self.client.oauth_session.client_secret,
            ATTR_LAST_SAVED_AT: int(time.time())
        }
        save_json(self.config_path, config_contents)
