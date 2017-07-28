"""
Support for Wink hubs.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/wink/
"""
import logging
import time
import json
import os
from datetime import timedelta

import voluptuous as vol
import requests

from homeassistant.loader import get_component
from homeassistant.core import callback
from homeassistant.components.http import HomeAssistantView
from homeassistant.helpers import discovery
from homeassistant.helpers.event import track_time_interval
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, CONF_EMAIL, CONF_PASSWORD,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP, __version__)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-wink==1.4.2', 'pubnubsub-handler==1.0.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'wink'

SUBSCRIPTION_HANDLER = None

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_USER_AGENT = 'user_agent'
CONF_OAUTH = 'oauth'
CONF_LOCAL_CONTROL = 'local_control'
CONF_APPSPOT = 'appspot'
CONF_MISSING_OAUTH_MSG = 'Missing oauth2 credentials.'
CONF_TOKEN_URL = "https://winkbearertoken.appspot.com/token"

ATTR_ACCESS_TOKEN = 'access_token'
ATTR_REFRESH_TOKEN = 'refresh_token'
ATTR_CLIENT_ID = 'client_id'
ATTR_CLIENT_SECRET = 'client_secret'

WINK_AUTH_CALLBACK_PATH = '/auth/wink/callback'
WINK_AUTH_START = '/auth/wink'
WINK_CONFIG_FILE = '.wink.conf'
USER_AGENT = "Manufacturer/Home-Assistant%s python/3 Wink/3" % (__version__)

DEFAULT_CONFIG = {
    'client_id': 'CLIENT_ID_HERE',
    'client_secret': 'CLIENT_SECRET_HERE'
}

SERVICE_ADD_NEW_DEVICES = 'add_new_devices'
SERVICE_REFRESH_STATES = 'refresh_state_from_wink'
SERVICE_KEEP_ALIVE = 'keep_pubnub_updates_flowing'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Inclusive(CONF_EMAIL, CONF_APPSPOT,
                      msg=CONF_MISSING_OAUTH_MSG): cv.string,
        vol.Inclusive(CONF_PASSWORD, CONF_APPSPOT,
                      msg=CONF_MISSING_OAUTH_MSG): cv.string,
        vol.Inclusive(CONF_CLIENT_ID, CONF_OAUTH,
                      msg=CONF_MISSING_OAUTH_MSG): cv.string,
        vol.Inclusive(CONF_CLIENT_SECRET, CONF_OAUTH,
                      msg=CONF_MISSING_OAUTH_MSG): cv.string,
        vol.Optional(CONF_LOCAL_CONTROL, default=False): cv.boolean
    })
}, extra=vol.ALLOW_EXTRA)

WINK_COMPONENTS = [
    'binary_sensor', 'sensor', 'light', 'switch', 'lock', 'cover', 'climate',
    'fan', 'alarm_control_panel', 'scene'
]


def _write_config_file(file_path, config):
    try:
        with open(file_path, 'w') as conf_file:
            conf_file.write(json.dumps(config, sort_keys=True, indent=4))
    except IOError as error:
        _LOGGER.error("Saving config file failed: %s", error)
        raise IOError("Saving Wink config file failed")
    return config


def _read_config_file(file_path):
    try:
        with open(file_path, 'r') as conf_file:
            return json.loads(conf_file.read())
    except IOError as error:
        _LOGGER.error("Reading config file failed: %s", error)
        raise IOError("Reading Wink config file failed")


def _request_app_setup(hass, config):
    """Assist user with configuring the Wink dev application."""
    hass.data[DOMAIN]['configurator'] = True
    configurator = get_component('configurator')

    # pylint: disable=unused-argument
    def wink_configuration_callback(callback_data):
        """Handle configuration updates."""
        _config_path = hass.config.path(WINK_CONFIG_FILE)
        if not os.path.isfile(_config_path):
            setup(hass, config)
            return

        client_id = callback_data.get('client_id')
        client_secret = callback_data.get('client_secret')
        if None not in (client_id, client_secret):
            _write_config_file(_config_path,
                               {ATTR_CLIENT_ID: client_id,
                                ATTR_CLIENT_SECRET: client_secret})
            setup(hass, config)
            return
        else:
            error_msg = ("Your input was invalid. Please try again.")
            _configurator = hass.data[DOMAIN]['configuring'][DOMAIN]
            configurator.notify_errors(_configurator, error_msg)

    start_url = "{}{}".format(hass.config.api.base_url,
                              WINK_AUTH_CALLBACK_PATH)

    description = """Please create a Wink developer app at
                     https://developer.wink.com.
                     Add a Redirect URI of {}.
                     They will provide you a Client ID and secret
                     after reviewing your request.
                     (This can take several days).
                     """.format(start_url)

    hass.data[DOMAIN]['configuring'][DOMAIN] = configurator.request_config(
        hass, DOMAIN, wink_configuration_callback,
        description=description, submit_caption="submit",
        description_image="/static/images/config_wink.png",
        fields=[{'id': 'client_id', 'name': 'Client ID', 'type': 'string'},
                {'id': 'client_secret',
                 'name': 'Client secret',
                 'type': 'string'}]
    )


def _request_oauth_completion(hass, config):
    """Request user complete Wink OAuth2 flow."""
    hass.data[DOMAIN]['configurator'] = True
    configurator = get_component('configurator')
    if DOMAIN in hass.data[DOMAIN]['configuring']:
        configurator.notify_errors(
            hass.data[DOMAIN]['configuring'][DOMAIN],
            "Failed to register, please try again.")
        return

    # pylint: disable=unused-argument
    def wink_configuration_callback(callback_data):
        """Call setup again."""
        setup(hass, config)

    start_url = '{}{}'.format(hass.config.api.base_url, WINK_AUTH_START)

    description = "Please authorize Wink by visiting {}".format(start_url)

    hass.data[DOMAIN]['configuring'][DOMAIN] = configurator.request_config(
        hass, DOMAIN, wink_configuration_callback,
        description=description
    )


def setup(hass, config):
    """Set up the Wink component."""
    import pywink
    from pubnubsubhandler import PubNubSubscriptionHandler

    if hass.data.get(DOMAIN) is None:
        hass.data[DOMAIN] = {
            'unique_ids': [],
            'entities': {},
            'oauth': {},
            'configuring': {},
            'pubnub': None,
            'configurator': False
        }

    def _get_wink_token_from_web():
        _email = hass.data[DOMAIN]["oauth"]["email"]
        _password = hass.data[DOMAIN]["oauth"]["password"]

        payload = {'username': _email, 'password': _password}
        token_response = requests.post(CONF_TOKEN_URL, data=payload)
        try:
            token = token_response.text.split(':')[1].split()[0].rstrip('<br')
        except IndexError:
            _LOGGER.error("Error getting token. Please check email/password.")
            return False
        pywink.set_bearer_token(token)

    client_id = config[DOMAIN].get(ATTR_CLIENT_ID)
    client_secret = config[DOMAIN].get(ATTR_CLIENT_SECRET)
    email = config[DOMAIN].get(CONF_EMAIL)
    password = config[DOMAIN].get(CONF_PASSWORD)
    local_control = config[DOMAIN].get(CONF_LOCAL_CONTROL)
    if None not in [client_id, client_secret]:
        _LOGGER.info("Using legacy oauth authentication")
        if not local_control:
            pywink.disable_local_control()
        hass.data[DOMAIN]["oauth"]["client_id"] = client_id
        hass.data[DOMAIN]["oauth"]["client_secret"] = client_secret
        hass.data[DOMAIN]["oauth"]["email"] = email
        hass.data[DOMAIN]["oauth"]["password"] = password
        pywink.legacy_set_wink_credentials(email, password,
                                           client_id, client_secret)
    elif None not in [email, password]:
        _LOGGER.info("Using web form authentication")
        pywink.disable_local_control()
        hass.data[DOMAIN]["oauth"]["email"] = email
        hass.data[DOMAIN]["oauth"]["password"] = password
        _get_wink_token_from_web()
    else:
        _LOGGER.info("Using new oauth authentication")
        if not local_control:
            pywink.disable_local_control()
        config_path = hass.config.path(WINK_CONFIG_FILE)
        if os.path.isfile(config_path):
            config_file = _read_config_file(config_path)
            if config_file == DEFAULT_CONFIG:
                _request_app_setup(hass, config)
                return True
            # else move on because the user modified the file
        else:
            _write_config_file(config_path, DEFAULT_CONFIG)
            _request_app_setup(hass, config)
            return True

        if DOMAIN in hass.data[DOMAIN]['configuring']:
            _configurator = hass.data[DOMAIN]['configuring']
            get_component('configurator').request_done(_configurator.pop(
                DOMAIN))

        # Using oauth
        access_token = config_file.get(ATTR_ACCESS_TOKEN)
        refresh_token = config_file.get(ATTR_REFRESH_TOKEN)

        # This will be called after authorizing Home-Assistant
        if None not in (access_token, refresh_token):
            pywink.set_wink_credentials(config_file.get(ATTR_CLIENT_ID),
                                        config_file.get(ATTR_CLIENT_SECRET),
                                        access_token=access_token,
                                        refresh_token=refresh_token)
        # This is called to create the redirect so the user can Authorize
        # Home-Assistant
        else:

            redirect_uri = '{}{}'.format(hass.config.api.base_url,
                                         WINK_AUTH_CALLBACK_PATH)

            wink_auth_start_url = pywink.get_authorization_url(
                config_file.get(ATTR_CLIENT_ID), redirect_uri)
            hass.http.register_redirect(WINK_AUTH_START, wink_auth_start_url)
            hass.http.register_view(WinkAuthCallbackView(config,
                                                         config_file,
                                                         pywink.request_token))
            _request_oauth_completion(hass, config)
            return True

    pywink.set_user_agent(USER_AGENT)
    hass.data[DOMAIN]['pubnub'] = PubNubSubscriptionHandler(
        pywink.get_subscription_key())

    def _subscribe():
        hass.data[DOMAIN]['pubnub'].subscribe()

    # Call subscribe after the user sets up wink via the configurator
    # All other methods will complete setup before
    # EVENT_HOMEASSISTANT_START is called meaning they
    # will call subscribe via the method below. (start_subscription)
    if hass.data[DOMAIN]['configurator']:
        _subscribe()

    def keep_alive_call(event_time):
        """Call the Wink API endpoints to keep PubNub working."""
        _LOGGER.info("Polling the Wink API to keep PubNub updates flowing.")
        pywink.set_user_agent(str(int(time.time())))
        _temp_response = pywink.get_user()
        _LOGGER.debug(str(json.dumps(_temp_response)))
        time.sleep(1)
        pywink.set_user_agent(USER_AGENT)
        _temp_response = pywink.wink_api_fetch()
        _LOGGER.debug(str(json.dumps(_temp_response)))

    # Call the Wink API every hour to keep PubNub updates flowing
    track_time_interval(hass, keep_alive_call, timedelta(minutes=60))

    def start_subscription(event):
        """Start the pubnub subscription."""
        _subscribe()

    hass.bus.listen(EVENT_HOMEASSISTANT_START, start_subscription)

    def stop_subscription(event):
        """Stop the pubnub subscription."""
        hass.data[DOMAIN]['pubnub'].unsubscribe()

    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, stop_subscription)

    def save_credentials(event):
        """Save currently set oauth credentials."""
        if hass.data[DOMAIN]["oauth"].get("email") is None:
            config_path = hass.config.path(WINK_CONFIG_FILE)
            _config = pywink.get_current_oauth_credentials()
            _write_config_file(config_path, _config)

    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, save_credentials)

    def force_update(call):
        """Force all devices to poll the Wink API."""
        _LOGGER.info("Refreshing Wink states from API")
        for entity_list in hass.data[DOMAIN]['entities'].values():
            # Throttle the calls to Wink API
            for entity in entity_list:
                time.sleep(1)
                entity.schedule_update_ha_state(True)
    hass.services.register(DOMAIN, SERVICE_REFRESH_STATES, force_update)

    def pull_new_devices(call):
        """Pull new devices added to users Wink account since startup."""
        _LOGGER.info("Getting new devices from Wink API")
        for _component in WINK_COMPONENTS:
            discovery.load_platform(hass, _component, DOMAIN, {}, config)

    hass.services.register(DOMAIN, SERVICE_ADD_NEW_DEVICES, pull_new_devices)

    # Load components for the devices in Wink that we support
    for component in WINK_COMPONENTS:
        hass.data[DOMAIN]['entities'][component] = []
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


class WinkAuthCallbackView(HomeAssistantView):
    """Handle OAuth finish callback requests."""

    url = '/auth/wink/callback'
    name = 'auth:wink:callback'
    requires_auth = False

    def __init__(self, config, config_file, request_token):
        """Initialize the OAuth callback view."""
        self.config = config
        self.config_file = config_file
        self.request_token = request_token

    @callback
    def get(self, request):
        """Finish OAuth callback request."""
        from aiohttp import web

        hass = request.app['hass']
        data = request.GET

        response_message = """Wink has been successfully authorized!
         You can close this window now! For the best results you should reboot
         HomeAssistant"""
        html_response = """<html><head><title>Wink Auth</title></head>
                <body><h1>{}</h1></body></html>"""

        if data.get('code') is not None:
            response = self.request_token(data.get('code'),
                                          self.config_file["client_secret"])

            config_contents = {
                ATTR_ACCESS_TOKEN: response['access_token'],
                ATTR_REFRESH_TOKEN: response['refresh_token'],
                ATTR_CLIENT_ID: self.config_file["client_id"],
                ATTR_CLIENT_SECRET: self.config_file["client_secret"]
            }
            _write_config_file(hass.config.path(WINK_CONFIG_FILE),
                               config_contents)

            hass.async_add_job(setup, hass, self.config)

            return web.Response(text=html_response.format(response_message),
                                content_type='text/html')

        error_msg = "No code returned from Wink API"
        _LOGGER.error(error_msg)
        return web.Response(text=html_response.format(error_msg),
                            content_type='text/html')


class WinkDevice(Entity):
    """Representation a base Wink device."""

    def __init__(self, wink, hass):
        """Initialize the Wink device."""
        self.hass = hass
        self.wink = wink
        hass.data[DOMAIN]['pubnub'].add_subscription(
            self.wink.pubnub_channel, self._pubnub_update)
        hass.data[DOMAIN]['unique_ids'].append(self.wink.object_id() +
                                               self.wink.name())

    def _pubnub_update(self, message):
        try:
            if message is None:
                _LOGGER.error("Error on pubnub update for %s "
                              "polling API for current state", self.name)
                self.schedule_update_ha_state(True)
            else:
                self.wink.pubnub_update(message)
                self.schedule_update_ha_state()
        except (ValueError, KeyError, AttributeError):
            _LOGGER.error("Error in pubnub JSON for %s "
                          "polling API for current state", self.name)
            self.schedule_update_ha_state(True)

    @property
    def name(self):
        """Return the name of the device."""
        return self.wink.name()

    @property
    def available(self):
        """Return true if connection == True."""
        return self.wink.available()

    def update(self):
        """Update state of the device."""
        self.wink.update_state()

    @property
    def should_poll(self):
        """Only poll if we are not subscribed to pubnub."""
        return self.wink.pubnub_channel is None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attributes = {}
        battery = self._battery_level
        if battery:
            attributes[ATTR_BATTERY_LEVEL] = battery
        man_dev_model = self._manufacturer_device_model
        if man_dev_model:
            attributes["manufacturer_device_model"] = man_dev_model
        man_dev_id = self._manufacturer_device_id
        if man_dev_id:
            attributes["manufacturer_device_id"] = man_dev_id
        dev_man = self._device_manufacturer
        if dev_man:
            attributes["device_manufacturer"] = dev_man
        model_name = self._model_name
        if model_name:
            attributes["model_name"] = model_name
        tamper = self._tamper
        if tamper is not None:
            attributes["tamper_detected"] = tamper
        return attributes

    @property
    def _battery_level(self):
        """Return the battery level."""
        if self.wink.battery_level() is not None:
            return self.wink.battery_level() * 100

    @property
    def _manufacturer_device_model(self):
        """Return the manufacturer device model."""
        return self.wink.manufacturer_device_model()

    @property
    def _manufacturer_device_id(self):
        """Return the manufacturer device id."""
        return self.wink.manufacturer_device_id()

    @property
    def _device_manufacturer(self):
        """Return the device manufacturer."""
        return self.wink.device_manufacturer()

    @property
    def _model_name(self):
        """Return the model name."""
        return self.wink.model_name()

    @property
    def _tamper(self):
        """Return the devices tamper status."""
        if hasattr(self.wink, 'tamper_detected'):
            return self.wink.tamper_detected()
        return None
