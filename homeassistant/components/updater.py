"""
homeassistant.components.updater
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates when a new update for HA is available
"""
# system imports
import logging
import os
import requests

# homeassistant imports
import homeassistant
from homeassistant import bootstrap

# homeassistant constants
DOMAIN = "updater"
DEPENDENCIES = []
REQUIREMENTS = ['requests>=2.0', 'gitpython>1.0.1']
CONF_PID_FILE = "pid_file"
HA_SOURCE_DIR = os.path.abspath(os.path.join(homeassistant.__file__, '..'))
SCAN_INTERVAL = 60 * 60 * 12

# setup logger
_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """
    Setup updater component.
    """
    # get optional configuration
    pid_file = config.get(CONF_PID_FILE, None)

    # create component entity
    Updater(hass, pid_file)

    return True

class Updater(object):

    hass = None
    entity_id = 'updater.updater'

    def __init__(self, hass, pid_file):
        self.pid_file = pid_file
        hass.track_time_change(self.update, hour=0, minute=0, second=0)

    def update(self, *args, **kwargs):
        github_resp = requests.get('https://api.github.com/repos/balloob/'
                                   + 'home-assistant/commits?sha=master')
        github_data = github_resp.json()
        newest_sha = github_data[0]['sha']
        newest_msg = github_data[0]['commit']['data']

    @property
    def atttributes(self):
        return {}

    def update_ha_state(self):
        pass
