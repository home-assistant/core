"""
Support for Wink hubs.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/wink/
"""
import asyncio
from datetime import timedelta
import json
import logging
import os
import time

import voluptuous as vol

from homeassistant.components.http import HomeAssistantView
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, ATTR_ENTITY_ID, ATTR_NAME, CONF_EMAIL, CONF_PASSWORD,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, STATE_OFF, STATE_ON,
    __version__)
from homeassistant.core import callback
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import track_time_interval
from homeassistant.util.json import load_json, save_json

REQUIREMENTS = ['python-wink==1.10.1', 'pubnubsub-handler==1.0.2']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'wink'

SUBSCRIPTION_HANDLER = None

CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_USER_AGENT = 'user_agent'
CONF_OAUTH = 'oauth'
CONF_LOCAL_CONTROL = 'local_control'
CONF_MISSING_OAUTH_MSG = 'Missing oauth2 credentials.'

ATTR_ACCESS_TOKEN = 'access_token'
ATTR_REFRESH_TOKEN = 'refresh_token'
ATTR_CLIENT_ID = 'client_id'
ATTR_CLIENT_SECRET = 'client_secret'
ATTR_PAIRING_MODE = 'pairing_mode'
ATTR_KIDDE_RADIO_CODE = 'kidde_radio_code'
ATTR_HUB_NAME = 'hub_name'

WINK_AUTH_CALLBACK_PATH = '/auth/wink/callback'
WINK_AUTH_START = '/auth/wink'
WINK_CONFIG_FILE = '.wink.conf'
USER_AGENT = "Manufacturer/Home-Assistant{} python/3 Wink/3".format(
    __version__)

DEFAULT_CONFIG = {
    'client_id': 'CLIENT_ID_HERE',
    'client_secret': 'CLIENT_SECRET_HERE'
}

SERVICE_ADD_NEW_DEVICES = 'pull_newly_added_devices_from_wink'
SERVICE_REFRESH_STATES = 'refresh_state_from_wink'
SERVICE_RENAME_DEVICE = 'rename_wink_device'
SERVICE_DELETE_DEVICE = 'delete_wink_device'
SERVICE_SET_PAIRING_MODE = 'pair_new_device'
SERVICE_SET_CHIME_VOLUME = "set_chime_volume"
SERVICE_SET_SIREN_VOLUME = "set_siren_volume"
SERVICE_ENABLE_CHIME = "enable_chime"
SERVICE_SET_SIREN_TONE = "set_siren_tone"
SERVICE_SET_AUTO_SHUTOFF = "siren_set_auto_shutoff"
SERVICE_SIREN_STROBE_ENABLED = "set_siren_strobe_enabled"
SERVICE_CHIME_STROBE_ENABLED = "set_chime_strobe_enabled"
SERVICE_ENABLE_SIREN = "enable_siren"
SERVICE_SET_DIAL_CONFIG = "set_nimbus_dial_configuration"
SERVICE_SET_DIAL_STATE = "set_nimbus_dial_state"

ATTR_VOLUME = "volume"
ATTR_TONE = "tone"
ATTR_ENABLED = "enabled"
ATTR_AUTO_SHUTOFF = "auto_shutoff"
ATTR_MIN_VALUE = "min_value"
ATTR_MAX_VALUE = "max_value"
ATTR_ROTATION = "rotation"
ATTR_SCALE = "scale"
ATTR_TICKS = "ticks"
ATTR_MIN_POSITION = "min_position"
ATTR_MAX_POSITION = "max_position"
ATTR_VALUE = "value"
ATTR_LABELS = "labels"

SCALES = ["linear", "log"]
ROTATIONS = ["cw", "ccw"]

VOLUMES = ["low", "medium", "high"]
TONES = ["doorbell", "fur_elise", "doorbell_extended", "alert",
         "william_tell", "rondo_alla_turca", "police_siren",
         "evacuation", "beep_beep", "beep"]
CHIME_TONES = TONES + ["inactive"]
AUTO_SHUTOFF_TIMES = [None, -1, 30, 60, 120]

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Inclusive(CONF_EMAIL, CONF_OAUTH,
                      msg=CONF_MISSING_OAUTH_MSG): cv.string,
        vol.Inclusive(CONF_PASSWORD, CONF_OAUTH,
                      msg=CONF_MISSING_OAUTH_MSG): cv.string,
        vol.Inclusive(CONF_CLIENT_ID, CONF_OAUTH,
                      msg=CONF_MISSING_OAUTH_MSG): cv.string,
        vol.Inclusive(CONF_CLIENT_SECRET, CONF_OAUTH,
                      msg=CONF_MISSING_OAUTH_MSG): cv.string,
        vol.Optional(CONF_LOCAL_CONTROL, default=False): cv.boolean
    })
}, extra=vol.ALLOW_EXTRA)

RENAME_DEVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_NAME): cv.string
}, extra=vol.ALLOW_EXTRA)

DELETE_DEVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids
}, extra=vol.ALLOW_EXTRA)

SET_PAIRING_MODE_SCHEMA = vol.Schema({
    vol.Required(ATTR_HUB_NAME): cv.string,
    vol.Required(ATTR_PAIRING_MODE): cv.string,
    vol.Optional(ATTR_KIDDE_RADIO_CODE): cv.string
}, extra=vol.ALLOW_EXTRA)

SET_VOLUME_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_VOLUME): vol.In(VOLUMES)
})

SET_SIREN_TONE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_TONE): vol.In(TONES)
})

SET_CHIME_MODE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_TONE): vol.In(CHIME_TONES)
})

SET_AUTO_SHUTOFF_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_AUTO_SHUTOFF): vol.In(AUTO_SHUTOFF_TIMES)
})

SET_STROBE_ENABLED_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_ENABLED): cv.boolean
})

ENABLED_SIREN_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_ENABLED): cv.boolean
})

DIAL_CONFIG_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Optional(ATTR_MIN_VALUE): vol.Coerce(int),
    vol.Optional(ATTR_MAX_VALUE): vol.Coerce(int),
    vol.Optional(ATTR_MIN_POSITION): cv.positive_int,
    vol.Optional(ATTR_MAX_POSITION): cv.positive_int,
    vol.Optional(ATTR_ROTATION): vol.In(ROTATIONS),
    vol.Optional(ATTR_SCALE): vol.In(SCALES),
    vol.Optional(ATTR_TICKS): cv.positive_int
})

DIAL_STATE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
    vol.Required(ATTR_VALUE): vol.Coerce(int),
    vol.Optional(ATTR_LABELS): cv.ensure_list(cv.string)
})

WINK_COMPONENTS = [
    'binary_sensor', 'sensor', 'light', 'switch', 'lock', 'cover', 'climate',
    'fan', 'alarm_control_panel', 'scene'
]

WINK_HUBS = []


def _request_app_setup(hass, config):
    """Assist user with configuring the Wink dev application."""
    hass.data[DOMAIN]['configurator'] = True
    configurator = hass.components.configurator

    def wink_configuration_callback(callback_data):
        """Handle configuration updates."""
        _config_path = hass.config.path(WINK_CONFIG_FILE)
        if not os.path.isfile(_config_path):
            setup(hass, config)
            return

        client_id = callback_data.get('client_id').strip()
        client_secret = callback_data.get('client_secret').strip()
        if None not in (client_id, client_secret):
            save_json(_config_path,
                      {ATTR_CLIENT_ID: client_id,
                       ATTR_CLIENT_SECRET: client_secret})
            setup(hass, config)
            return
        error_msg = "Your input was invalid. Please try again."
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
        DOMAIN, wink_configuration_callback,
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
    configurator = hass.components.configurator
    if DOMAIN in hass.data[DOMAIN]['configuring']:
        configurator.notify_errors(
            hass.data[DOMAIN]['configuring'][DOMAIN],
            "Failed to register, please try again.")
        return

    def wink_configuration_callback(callback_data):
        """Call setup again."""
        setup(hass, config)

    start_url = '{}{}'.format(hass.config.api.base_url, WINK_AUTH_START)

    description = "Please authorize Wink by visiting {}".format(start_url)

    hass.data[DOMAIN]['configuring'][DOMAIN] = configurator.request_config(
        DOMAIN, wink_configuration_callback, description=description)


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

    if config.get(DOMAIN) is not None:
        client_id = config[DOMAIN].get(ATTR_CLIENT_ID)
        client_secret = config[DOMAIN].get(ATTR_CLIENT_SECRET)
        email = config[DOMAIN].get(CONF_EMAIL)
        password = config[DOMAIN].get(CONF_PASSWORD)
        local_control = config[DOMAIN].get(CONF_LOCAL_CONTROL)
    else:
        client_id = None
        client_secret = None
        email = None
        password = None
        local_control = None
        hass.data[DOMAIN]['configurator'] = True
    if None not in [client_id, client_secret]:
        _LOGGER.info("Using legacy OAuth authentication")
        if not local_control:
            pywink.disable_local_control()
        hass.data[DOMAIN]["oauth"]["client_id"] = client_id
        hass.data[DOMAIN]["oauth"]["client_secret"] = client_secret
        hass.data[DOMAIN]["oauth"]["email"] = email
        hass.data[DOMAIN]["oauth"]["password"] = password
        pywink.legacy_set_wink_credentials(email, password,
                                           client_id, client_secret)
    else:
        _LOGGER.info("Using OAuth authentication")
        if not local_control:
            pywink.disable_local_control()
        config_path = hass.config.path(WINK_CONFIG_FILE)
        if os.path.isfile(config_path):
            config_file = load_json(config_path)
            if config_file == DEFAULT_CONFIG:
                _request_app_setup(hass, config)
                return True
            # else move on because the user modified the file
        else:
            save_json(config_path, DEFAULT_CONFIG)
            _request_app_setup(hass, config)
            return True

        if DOMAIN in hass.data[DOMAIN]['configuring']:
            _configurator = hass.data[DOMAIN]['configuring']
            hass.components.configurator.request_done(_configurator.pop(
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
        # Home .
        else:

            redirect_uri = '{}{}'.format(
                hass.config.api.base_url, WINK_AUTH_CALLBACK_PATH)

            wink_auth_start_url = pywink.get_authorization_url(
                config_file.get(ATTR_CLIENT_ID), redirect_uri)
            hass.http.register_redirect(WINK_AUTH_START, wink_auth_start_url)
            hass.http.register_view(WinkAuthCallbackView(
                config, config_file, pywink.request_token))
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
        _LOGGER.info("Polling the Wink API to keep PubNub updates flowing")
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
        """Start the PubNub subscription."""
        _subscribe()

    hass.bus.listen(EVENT_HOMEASSISTANT_START, start_subscription)

    def stop_subscription(event):
        """Stop the PubNub subscription."""
        hass.data[DOMAIN]['pubnub'].unsubscribe()
        hass.data[DOMAIN]['pubnub'] = None

    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, stop_subscription)

    def save_credentials(event):
        """Save currently set OAuth credentials."""
        if hass.data[DOMAIN]["oauth"].get("email") is None:
            config_path = hass.config.path(WINK_CONFIG_FILE)
            _config = pywink.get_current_oauth_credentials()
            save_json(config_path, _config)

    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, save_credentials)

    # Save the users potentially updated oauth credentials at a regular
    # interval to prevent them from being expired after a HA reboot.
    track_time_interval(hass, save_credentials, timedelta(minutes=60))

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

    def set_pairing_mode(call):
        """Put the hub in provided pairing mode."""
        hub_name = call.data.get('hub_name')
        pairing_mode = call.data.get('pairing_mode')
        kidde_code = call.data.get('kidde_radio_code')
        for hub in WINK_HUBS:
            if hub.name() == hub_name:
                hub.pair_new_device(pairing_mode, kidde_radio_code=kidde_code)

    def rename_device(call):
        """Set specified device's name."""
        # This should only be called on one device at a time.
        found_device = None
        entity_id = call.data.get('entity_id')[0]
        all_devices = []
        for list_of_devices in hass.data[DOMAIN]['entities'].values():
            all_devices += list_of_devices
        for device in all_devices:
            if device.entity_id == entity_id:
                found_device = device
        if found_device is not None:
            name = call.data.get('name')
            found_device.wink.set_name(name)

    hass.services.register(DOMAIN, SERVICE_RENAME_DEVICE, rename_device,
                           schema=RENAME_DEVICE_SCHEMA)

    def delete_device(call):
        """Delete specified device."""
        # This should only be called on one device at a time.
        found_device = None
        entity_id = call.data.get('entity_id')[0]
        all_devices = []
        for list_of_devices in hass.data[DOMAIN]['entities'].values():
            all_devices += list_of_devices
        for device in all_devices:
            if device.entity_id == entity_id:
                found_device = device
        if found_device is not None:
            found_device.wink.remove_device()

    hass.services.register(DOMAIN, SERVICE_DELETE_DEVICE, delete_device,
                           schema=DELETE_DEVICE_SCHEMA)

    hubs = pywink.get_hubs()
    for hub in hubs:
        if hub.device_manufacturer() == 'wink':
            WINK_HUBS.append(hub)

    if WINK_HUBS:
        hass.services.register(
            DOMAIN, SERVICE_SET_PAIRING_MODE, set_pairing_mode,
            schema=SET_PAIRING_MODE_SCHEMA)

    def nimbus_service_handle(service):
        """Handle nimbus services."""
        entity_id = service.data.get('entity_id')[0]
        _all_dials = []
        for sensor in hass.data[DOMAIN]['entities']['sensor']:
            if isinstance(sensor, WinkNimbusDialDevice):
                _all_dials.append(sensor)
        for _dial in _all_dials:
            if _dial.entity_id == entity_id:
                if service.service == SERVICE_SET_DIAL_CONFIG:
                    _dial.set_configuration(**service.data)
                if service.service == SERVICE_SET_DIAL_STATE:
                    _dial.wink.set_state(service.data.get("value"),
                                         service.data.get("labels"))

    def siren_service_handle(service):
        """Handle siren services."""
        entity_ids = service.data.get('entity_id')
        all_sirens = []
        for switch in hass.data[DOMAIN]['entities']['switch']:
            if isinstance(switch, WinkSirenDevice):
                all_sirens.append(switch)
        sirens_to_set = []
        if entity_ids is None:
            sirens_to_set = all_sirens
        else:
            for siren in all_sirens:
                if siren.entity_id in entity_ids:
                    sirens_to_set.append(siren)

        for siren in sirens_to_set:
            _man = siren.wink.device_manufacturer()
            if (service.service != SERVICE_SET_AUTO_SHUTOFF and
                    service.service != SERVICE_ENABLE_SIREN and
                    _man not in ('dome', 'wink')):
                _LOGGER.error("Service only valid for Dome or Wink sirens")
                return

            if service.service == SERVICE_ENABLE_SIREN:
                siren.wink.set_state(service.data.get(ATTR_ENABLED))
            elif service.service == SERVICE_SET_AUTO_SHUTOFF:
                siren.wink.set_auto_shutoff(
                    service.data.get(ATTR_AUTO_SHUTOFF))
            elif service.service == SERVICE_SET_CHIME_VOLUME:
                siren.wink.set_chime_volume(service.data.get(ATTR_VOLUME))
            elif service.service == SERVICE_SET_SIREN_VOLUME:
                siren.wink.set_siren_volume(service.data.get(ATTR_VOLUME))
            elif service.service == SERVICE_SET_SIREN_TONE:
                siren.wink.set_siren_sound(service.data.get(ATTR_TONE))
            elif service.service == SERVICE_ENABLE_CHIME:
                siren.wink.set_chime(service.data.get(ATTR_TONE))
            elif service.service == SERVICE_SIREN_STROBE_ENABLED:
                siren.wink.set_siren_strobe_enabled(
                    service.data.get(ATTR_ENABLED))
            elif service.service == SERVICE_CHIME_STROBE_ENABLED:
                siren.wink.set_chime_strobe_enabled(
                    service.data.get(ATTR_ENABLED))

    # Load components for the devices in Wink that we support
    for wink_component in WINK_COMPONENTS:
        hass.data[DOMAIN]['entities'][wink_component] = []
        discovery.load_platform(hass, wink_component, DOMAIN, {}, config)

    component = EntityComponent(_LOGGER, DOMAIN, hass)

    sirens = []
    has_dome_or_wink_siren = False
    for siren in pywink.get_sirens():
        _man = siren.device_manufacturer()
        if _man in ("dome", "wink"):
            has_dome_or_wink_siren = True
        _id = siren.object_id() + siren.name()
        if _id not in hass.data[DOMAIN]['unique_ids']:
            sirens.append(WinkSirenDevice(siren, hass))

    if sirens:

        hass.services.register(DOMAIN, SERVICE_SET_AUTO_SHUTOFF,
                               siren_service_handle,
                               schema=SET_AUTO_SHUTOFF_SCHEMA)

        hass.services.register(DOMAIN, SERVICE_ENABLE_SIREN,
                               siren_service_handle,
                               schema=ENABLED_SIREN_SCHEMA)

    if has_dome_or_wink_siren:

        hass.services.register(DOMAIN, SERVICE_SET_SIREN_TONE,
                               siren_service_handle,
                               schema=SET_SIREN_TONE_SCHEMA)

        hass.services.register(DOMAIN, SERVICE_ENABLE_CHIME,
                               siren_service_handle,
                               schema=SET_CHIME_MODE_SCHEMA)

        hass.services.register(DOMAIN, SERVICE_SET_SIREN_VOLUME,
                               siren_service_handle,
                               schema=SET_VOLUME_SCHEMA)

        hass.services.register(DOMAIN, SERVICE_SET_CHIME_VOLUME,
                               siren_service_handle,
                               schema=SET_VOLUME_SCHEMA)

        hass.services.register(DOMAIN, SERVICE_SIREN_STROBE_ENABLED,
                               siren_service_handle,
                               schema=SET_STROBE_ENABLED_SCHEMA)

        hass.services.register(DOMAIN, SERVICE_CHIME_STROBE_ENABLED,
                               siren_service_handle,
                               schema=SET_STROBE_ENABLED_SCHEMA)

    component.add_entities(sirens)

    nimbi = []
    dials = {}
    all_nimbi = pywink.get_cloud_clocks()
    all_dials = []
    for nimbus in all_nimbi:
        if nimbus.object_type() == "cloud_clock":
            nimbi.append(nimbus)
            dials[nimbus.object_id()] = []
    for nimbus in all_nimbi:
        if nimbus.object_type() == "dial":
            dials[nimbus.parent_id()].append(nimbus)

    for nimbus in nimbi:
        for dial in dials[nimbus.object_id()]:
            all_dials.append(WinkNimbusDialDevice(nimbus, dial, hass))

    if nimbi:
        hass.services.register(DOMAIN, SERVICE_SET_DIAL_CONFIG,
                               nimbus_service_handle,
                               schema=DIAL_CONFIG_SCHEMA)

        hass.services.register(DOMAIN, SERVICE_SET_DIAL_STATE,
                               nimbus_service_handle,
                               schema=DIAL_STATE_SCHEMA)

    component.add_entities(all_dials)

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
        data = request.query

        response_message = """Wink has been successfully authorized!
         You can close this window now! For the best results you should reboot
         HomeAssistant"""
        html_response = """<html><head><title>Wink Auth</title></head>
                <body><h1>{}</h1></body></html>"""

        if data.get('code') is not None:
            response = self.request_token(
                data.get('code'), self.config_file['client_secret'])

            config_contents = {
                ATTR_ACCESS_TOKEN: response['access_token'],
                ATTR_REFRESH_TOKEN: response['refresh_token'],
                ATTR_CLIENT_ID: self.config_file['client_id'],
                ATTR_CLIENT_SECRET: self.config_file['client_secret']
            }
            save_json(hass.config.path(WINK_CONFIG_FILE), config_contents)

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
        _LOGGER.debug(message)
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


class WinkSirenDevice(WinkDevice):
    """Representation of a Wink siren device."""

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN]['entities']['switch'].append(self)

    @property
    def state(self):
        """Return sirens state."""
        if self.wink.state():
            return STATE_ON
        return STATE_OFF

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return "mdi:bell-ring"

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = super(WinkSirenDevice, self).device_state_attributes

        auto_shutoff = self.wink.auto_shutoff()
        if auto_shutoff is not None:
            attributes["auto_shutoff"] = auto_shutoff

        siren_volume = self.wink.siren_volume()
        if siren_volume is not None:
            attributes["siren_volume"] = siren_volume

        chime_volume = self.wink.chime_volume()
        if chime_volume is not None:
            attributes["chime_volume"] = chime_volume

        strobe_enabled = self.wink.strobe_enabled()
        if strobe_enabled is not None:
            attributes["siren_strobe_enabled"] = strobe_enabled

        chime_strobe_enabled = self.wink.chime_strobe_enabled()
        if chime_strobe_enabled is not None:
            attributes["chime_strobe_enabled"] = chime_strobe_enabled

        siren_sound = self.wink.siren_sound()
        if siren_sound is not None:
            attributes["siren_sound"] = siren_sound

        chime_mode = self.wink.chime_mode()
        if chime_mode is not None:
            attributes["chime_mode"] = chime_mode

        return attributes


class WinkNimbusDialDevice(WinkDevice):
    """Representation of the Quirky Nimbus device."""

    def __init__(self, nimbus, dial, hass):
        """Initialize the Nimbus dial."""
        super().__init__(dial, hass)
        self.parent = nimbus

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.data[DOMAIN]['entities']['sensor'].append(self)

    @property
    def state(self):
        """Return dials current value."""
        return self.wink.state()

    @property
    def name(self):
        """Return the name of the device."""
        return self.parent.name() + " dial " + str(self.wink.index() + 1)

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = super(WinkNimbusDialDevice, self).device_state_attributes
        dial_attributes = self.dial_attributes()

        return {**attributes, **dial_attributes}

    def dial_attributes(self):
        """Return the dial only attributes."""
        return {
            "labels": self.wink.labels(),
            "position": self.wink.position(),
            "rotation": self.wink.rotation(),
            "max_value": self.wink.max_value(),
            "min_value": self.wink.min_value(),
            "num_ticks": self.wink.ticks(),
            "scale_type": self.wink.scale(),
            "max_position": self.wink.max_position(),
            "min_position": self.wink.min_position()
        }

    def set_configuration(self, **kwargs):
        """
        Set the dial config.

        Anything not sent will default to current setting.
        """
        attributes = {**self.dial_attributes(), **kwargs}

        min_value = attributes["min_value"]
        max_value = attributes["max_value"]
        rotation = attributes["rotation"]
        ticks = attributes["num_ticks"]
        scale = attributes["scale_type"]
        min_position = attributes["min_position"]
        max_position = attributes["max_position"]

        self.wink.set_configuration(min_value, max_value, rotation,
                                    scale=scale, ticks=ticks,
                                    min_position=min_position,
                                    max_position=max_position)
