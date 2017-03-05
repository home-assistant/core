"""
Support for Wink hubs.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/wink/
"""
import logging

import voluptuous as vol

from homeassistant.helpers import discovery
from homeassistant.const import (
    CONF_ACCESS_TOKEN, ATTR_BATTERY_LEVEL, CONF_EMAIL, CONF_PASSWORD,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-wink==1.1.1', 'pubnubsub-handler==1.0.1']

_LOGGER = logging.getLogger(__name__)

CHANNELS = []

DOMAIN = 'wink'

SUBSCRIPTION_HANDLER = None
CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'
CONF_USER_AGENT = 'user_agent'
CONF_OATH = 'oath'
CONF_APPSPOT = 'appspot'
CONF_DEFINED_BOTH_MSG = 'Remove access token to use oath2.'
CONF_MISSING_OATH_MSG = 'Missing oath2 credentials.'
CONF_TOKEN_URL = "https://winkbearertoken.appspot.com/token"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Inclusive(CONF_EMAIL, CONF_APPSPOT,
                      msg=CONF_MISSING_OATH_MSG): cv.string,
        vol.Inclusive(CONF_PASSWORD, CONF_APPSPOT,
                      msg=CONF_MISSING_OATH_MSG): cv.string,
        vol.Inclusive(CONF_CLIENT_ID, CONF_OATH,
                      msg=CONF_MISSING_OATH_MSG): cv.string,
        vol.Inclusive(CONF_CLIENT_SECRET, CONF_OATH,
                      msg=CONF_MISSING_OATH_MSG): cv.string,
        vol.Exclusive(CONF_EMAIL, CONF_OATH,
                      msg=CONF_DEFINED_BOTH_MSG): cv.string,
        vol.Exclusive(CONF_ACCESS_TOKEN, CONF_OATH,
                      msg=CONF_DEFINED_BOTH_MSG): cv.string,
        vol.Exclusive(CONF_ACCESS_TOKEN, CONF_APPSPOT,
                      msg=CONF_DEFINED_BOTH_MSG): cv.string,
        vol.Optional(CONF_USER_AGENT, default=None): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

WINK_COMPONENTS = [
    'binary_sensor', 'sensor', 'light', 'switch', 'lock', 'cover', 'climate',
    'fan', 'alarm_control_panel'
]


def setup(hass, config):
    """Set up the Wink component."""
    import pywink
    import requests
    from pubnubsubhandler import PubNubSubscriptionHandler

    user_agent = config[DOMAIN].get(CONF_USER_AGENT)

    if user_agent:
        pywink.set_user_agent(user_agent)

    access_token = config[DOMAIN].get(CONF_ACCESS_TOKEN)
    client_id = config[DOMAIN].get('client_id')

    if access_token:
        pywink.set_bearer_token(access_token)
    elif client_id:
        email = config[DOMAIN][CONF_EMAIL]
        password = config[DOMAIN][CONF_PASSWORD]
        client_id = config[DOMAIN]['client_id']
        client_secret = config[DOMAIN]['client_secret']
        pywink.set_wink_credentials(email, password, client_id,
                                    client_secret)
    else:
        email = config[DOMAIN][CONF_EMAIL]
        password = config[DOMAIN][CONF_PASSWORD]
        payload = {'username': email, 'password': password}
        token_response = requests.post(CONF_TOKEN_URL, data=payload)
        try:
            token = token_response.text.split(':')[1].split()[0].rstrip('<br')
        except IndexError:
            _LOGGER.error("Error getting token. Please check email/password.")
            return False
        pywink.set_bearer_token(token)

    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]['entities'] = []
    hass.data[DOMAIN]['unique_ids'] = []
    hass.data[DOMAIN]['pubnub'] = PubNubSubscriptionHandler(
        pywink.get_subscription_key(),
        pywink.wink_api_fetch)

    def start_subscription(event):
        """Start the pubnub subscription."""
        hass.data[DOMAIN]['pubnub'].subscribe()
    hass.bus.listen(EVENT_HOMEASSISTANT_START, start_subscription)

    def stop_subscription(event):
        """Stop the pubnub subscription."""
        hass.data[DOMAIN]['pubnub'].unsubscribe()
    hass.bus.listen(EVENT_HOMEASSISTANT_STOP, stop_subscription)

    def force_update(call):
        """Force all devices to poll the Wink API."""
        _LOGGER.info("Refreshing Wink states from API")
        for entity in hass.data[DOMAIN]['entities']:
            entity.schedule_update_ha_state(True)
    hass.services.register(DOMAIN, 'Refresh state from Wink', force_update)

    def pull_new_devices(call):
        """Pull new devices added to users Wink account since startup."""
        _LOGGER.info("Getting new devices from Wink API.")
        for component in WINK_COMPONENTS:
            discovery.load_platform(hass, component, DOMAIN, {}, config)
    hass.services.register(DOMAIN, 'Add new devices', pull_new_devices)

    # Load components for the devices in Wink that we support
    for component in WINK_COMPONENTS:
        discovery.load_platform(hass, component, DOMAIN, {}, config)

    return True


class WinkDevice(Entity):
    """Representation a base Wink device."""

    def __init__(self, wink, hass):
        """Initialize the Wink device."""
        self.hass = hass
        self.wink = wink
        hass.data[DOMAIN]['pubnub'].add_subscription(
            self.wink.pubnub_channel, self._pubnub_update)
        hass.data[DOMAIN]['entities'].append(self)
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
        """True if connection == True."""
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
        else:
            return None
