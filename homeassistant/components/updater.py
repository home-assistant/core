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
REQUIREMENTS = ['requests>=2.0', 'gitpython>=1.0.1']
CONF_PID_FILE = "pid_file"
HA_SOURCE_DIR = os.path.abspath(os.path.join(homeassistant.__file__,
                                             '..', '..'))
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
    Updater(hass, pid_file, _LOGGER)

    return True


class Updater(object):

    hass = None
    entity_id = 'updater.updater'

    def __init__(self, hass, pid_file, logger):
        try:
            from git import Repo
        except ImportError:
            logger.error('Missing package gitpython')
            self._repo_class = None
        else:
            self._repo_class = Repo

        self.hass = hass
        self.pid_file = pid_file
        self._logger = logger

        hass.track_time_change(self.update, hour=0, minute=0, second=0)
        self.newest_sha = None
        self.newest_msg = None
        self.newest_date = None
        self.current_sha = None

        self.update()

    def update(self, *args, **kwargs):
        _LOGGER.info('Looking for updates.')
        # pull data from github
        github_resp = requests.get('https://api.github.com/repos/balloob/'
                                   + 'home-assistant/commits?sha=master')
        github_data = github_resp.json()
        self.newest_sha = github_data[0]['sha']
        self.newest_msg = github_data[0]['commit']['message']
        self.newest_date = github_data[0]['commit']['author']['date']

        # find local copy info
        if self._repo_class is not None:
            repo = self._repo_class(HA_SOURCE_DIR)
            if repo.bare:
                self.current_sha = None
            else:
                self.current_sha = repo.head.commit.hexsha
        else:
            self.current_sha = None

        # update with HA
        self.update_ha_state()

    @property
    def hidden(self):
        return self.current_sha == self.newest_sha

    @property
    def state(self):
        return False

    @property
    def attributes(self):
        return {'hidden': self.hidden, 'Local SHA': self.current_sha,
                'Remote SHA': self.newest_sha,
                'Message': '{}\n{}'.format(self.newest_date, self.newest_msg)}

    def update_ha_state(self):
        self.hass.states.set(self.entity_id, self.state, self.attributes)
