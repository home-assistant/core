DOMAIN = 'goalfeed'

REQUIREMENTS = ['pysher==0.1.2']

import json
# Add a logging handler so we can see the raw communication data
import logging
import sys
from io import StringIO

import requests

import pysher

root = logging.getLogger()
root.setLevel(logging.INFO)
ch = logging.StreamHandler(sys.stdout)
root.addHandler(ch)

global pusher

# GOALFEED_HOST = 'goalfeed.local'
GOALFEED_AUTH_ENDPOINT = 'http://goalfeed.local/feed/auth'

def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""
    
    def connect_handler(data):
        channel = pusher.subscribe('private-goals')
        channel.bind('goal', goal_handler)


    username = 'user'
    password = 'pass'
    post_data = {'username': username, 'password': password}

    response = requests.post(GOALFEED_AUTH_ENDPOINT, post_data).json()


    pusher = pysher.Pusher('bfd4ed98c1ff22c04074', secret=response['auth'])
    pusher.host = response['server']

    pusher.connection.bind('pusher:connection_established', connect_handler)
    pusher.connect()

    return True

    def goal_handler(data):
        goal = json.loads(json.loads(data))

        # Fire event my_cool_event with event data answer=42
        hass.bus.async_fire('goal', event_data={'team': goal['team_hash']})
