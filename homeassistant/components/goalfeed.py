DOMAIN = 'goalfeed'

REQUIREMENTS = ['https://github.com/wardcraigj/PythonPusherClient/archive/773e8223ccdceb535cd6f47ceb8b5e951a13beb3.zip#PythonPusherClient==0.3.0']

import pusherclient
import sys

# Add a logging handler so we can see the raw communication data
import logging
root = logging.getLogger()
root.setLevel(logging.INFO)
ch = logging.StreamHandler(sys.stdout)
root.addHandler(ch)
from io import StringIO
import json

global pusher

def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""
    
    def connect_handler(data):
        channel = pusher.subscribe('goals')
        channel.bind('goal', goal_handler)

    pusher = pusherclient.Pusher('bfd4ed98c1ff22c04074')
    pusher.host = 'ec2-54-186-137-237.us-west-2.compute.amazonaws.com'

    pusher.connection.bind('pusher:connection_established', connect_handler)
    pusher.connect()

    def goal_handler(data):
        goal = json.loads(json.loads(data))

        # Fire event my_cool_event with event data answer=42
        hass.bus.async_fire('goal', event_data={'team': goal['team_hash']})