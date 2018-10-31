"""
Component for the Goalfeed service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/goalfeed/
"""
import json

import requests
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

REQUIREMENTS = ['pysher==0.2.0']

DOMAIN = 'goalfeed'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

GOALFEED_HOST = 'feed.goalfeed.ca'
GOALFEED_AUTH_ENDPOINT = 'https://goalfeed.ca/feed/auth'
GOALFEED_APP_ID = 'bfd4ed98c1ff22c04074'


def setup(hass, config):
    """Set up the Goalfeed component."""
    import pysher
    conf = config[DOMAIN]
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD)

    def goal_handler(data):
        """Handle goal events."""
        goal = json.loads(json.loads(data))

        hass.bus.fire('goal', event_data=goal)

    def connect_handler(data):
        """Handle connection."""
        post_data = {
            'username': username,
            'password': password,
            'connection_info': data}
        resp = requests.post(GOALFEED_AUTH_ENDPOINT, post_data,
                             timeout=30).json()

        channel = pusher.subscribe('private-goals', resp['auth'])
        channel.bind('goal', goal_handler)

    pusher = pysher.Pusher(GOALFEED_APP_ID, secure=False, port=8080,
                           custom_host=GOALFEED_HOST)

    pusher.connection.bind('pusher:connection_established', connect_handler)
    pusher.connect()

    return True
