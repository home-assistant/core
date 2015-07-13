"""
homeassistant.components.updater
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Indicates when a new update for HA is available
"""
# system imports
import logging
import os
import requests
import subprocess

# homeassistant imports
import homeassistant
from homeassistant.helpers.entity import Entity

# homeassistant constants
DOMAIN = "updater"
DEPENDENCIES = []
REQUIREMENTS = ['requests>=2.0', 'gitpython>=1.0.1']
CONF_PID_FILE = "pid_file"
CONF_LOG_FILE = "log_file"
CONF_REPO_NAME = "repo_name"
CONF_REPO_BRANCH = "repo_branch"
HA_SOURCE_DIR = os.path.abspath(os.path.join(homeassistant.__file__,
                                             '..', '..'))
GH_API_CALL = 'https://api.github.com/repos/{repo}/commits?sha={branch}'
SCAN_INTERVAL = 60 * 60 * 12

# setup logger
_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """
    Setup updater component.
    """
    # get optional configuration
    pid_file = config['updater'].get(CONF_PID_FILE, None)
    log_file = config['updater'].get(CONF_LOG_FILE, None)
    repo_name = config['updater'].get(CONF_REPO_NAME, 'balloob/home-assistant')
    repo_branch = config['updater'].get(CONF_REPO_BRANCH, 'master')

    # create component entity
    Updater(hass, _LOGGER, repo_name=repo_name, repo_branch=repo_branch,
            pid_file=pid_file, log_file=log_file)

    return True


class Updater(Entity):
    """ Updater entity class """

    hass = None
    entity_id = 'updater.updater'
    name = 'Updater'

    def __init__(self, hass, logger, **kwargs):
        try:
            from git import Repo
        except ImportError:
            logger.error('Missing package gitpython')
            self._repo_class = None
        else:
            self._repo_class = Repo

        self.hass = hass
        self._logger = logger

        self.config = kwargs

        hass.track_time_change(self.update, hour=0, minute=0, second=0)
        self.hass.services.register(DOMAIN, 'update', self.run_update)

        self.versions = {'newest_sha': None,
                         'newest_msg': None,
                         'newest_date': None,
                         'newest_url': None,
                         'current_sha': None}

        self.update()

    def update(self, *args, **kwargs):
        ''' Update the state of the entity '''
        _LOGGER.info('Looking for updates.')
        # pull data from github
        github_resp = requests.get(
            GH_API_CALL.format(repo=self.config['repo_name'],
                               branch=self.config['branch']))
        github_data = github_resp.json()
        if github_resp.headers['status'] == '200 OK':
            self.versions['newest_sha'] = github_data[0]['sha']
            self.versions['newest_msg'] = github_data[0]['commit']['message']
            self.versions['newest_date'] = \
                github_data[0]['commit']['author']['date']
            self.versions['newest_url'] = github_data[0]['html_url']

        # find local copy info
        if self._repo_class is not None:
            repo = self._repo_class(HA_SOURCE_DIR)
            if repo.bare:
                self.versions['current_sha'] = None
            else:
                self.versions['current_sha'] = repo.head.commit.hexsha
        else:
            self.versions['current_sha'] = None

        # update with HA
        self.update_ha_state()

    @property
    def hidden(self):
        ''' only show the entity when an update is available '''
        return not self.versions['newest_sha'] and \
            self.versions['current_sha'] == self.versions['newest_sha']

    @property
    def state(self):
        ''' Is an update available? '''
        return not self.hidden

    @property
    def state_attributes(self):
        ''' current entity state attributes '''
        return {'hidden': self.hidden,
                'local_sha': self.versions['current_sha'],
                'remote_sha': self.versions['newest_sha'],
                'message': self.versions['newest_msg'],
                'date': self.versions['newest_date'],
                'link': self.versions['newest_url']}

    def run_update(self, *args, **kwargs):
        ''' run the updater '''
        upscript = os.path.join(HA_SOURCE_DIR, 'scripts', 'update')
        mypid = str(os.getpid())
        cmd = [upscript, HA_SOURCE_DIR, mypid]

        if self.config['log_file'] is not None:
            cmd.append(self.config['log_file'])
            if self.config['pid_file'] is not None:
                cmd.append(self.config['pid_file'])

        subprocess.call(cmd)
