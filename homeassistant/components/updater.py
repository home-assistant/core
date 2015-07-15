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
REQUIREMENTS = ['gitpython>=1.0.1']
CONF_PID_FILE = "pid_file"
CONF_LOG_FILE = "log_file"
CONF_REPO_NAME = "repo_name"
CONF_REPO_BRANCH = "repo_branch"
HA_SOURCE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(homeassistant.__file__), '..'))
GH_API_CALL = 'https://api.github.com/repos/{repo}/commits?sha={branch}'

# setup logger
_LOGGER = logging.getLogger(__name__)


def setup(hass, config):
    """
    Setup updater component.
    """
    # get optional configuration
    pid_file = config[DOMAIN].get(CONF_PID_FILE, None)
    log_file = config[DOMAIN].get(CONF_LOG_FILE, None)
    repo_name = config[DOMAIN].get(CONF_REPO_NAME, 'balloob/home-assistant')
    repo_branch = config[DOMAIN].get(CONF_REPO_BRANCH, 'master')

    # create updater service
    def run_update(service_call):
        ''' run the updater '''
        upscript = os.path.join(HA_SOURCE_DIR, 'scripts', 'update')
        mypid = str(os.getpid())
        cmd = [upscript, HA_SOURCE_DIR, mypid]

        if log_file is not None:
            cmd.append(log_file)
            if pid_file is not None:
                cmd.append(pid_file)

        subprocess.call(cmd)
    hass.services.register(DOMAIN, 'update', run_update)

    # find local copy info
    try:
        from git import Repo
    except ImportError:
        _LOGGER.error('Missing package gitpython')
        return False
    else:
        repo = Repo(HA_SOURCE_DIR)
        if repo.bare:
            current_sha = None
        else:
            current_sha = repo.head.commit.hexsha

    # create component entity
    Updater(hass, current_sha, repo_name, repo_branch, pid_file, log_file)

    return True


class Updater(Entity):
    """ Updater entity class """

    hass = None
    entity_id = 'updater.updater'
    name = 'updater'

    def __init__(self, hass, current_sha, repo_name, branch, pid_file,
                 log_file):
        # pylint: disable=too-many-arguments
        self.hass = hass
        self.config = {'repo_name': repo_name, 'branch': branch,
                       'pid_file': pid_file, 'log_file': log_file}

        # register update check event
        def check_ha_update(event):
            """ Check GitHub for avaialable update """
            self.update()
        hass.track_time_change(check_ha_update, hour=0, minute=0, second=0)

        # initialize data
        self.versions = {'newest_sha': None, 'newest_msg': None,
                         'newest_date': None, 'newest_url': None,
                         'current_sha': current_sha}

        self.update()

    def update(self):
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

            # update with HA
            self.update_ha_state()
        else:
            _LOGGER.warning('Error communicating with GitHub')

    @property
    def hidden(self):
        ''' only show the entity when an update is available '''
        return self._state_raw

    @property
    def state(self):
        ''' Is an update available? '''
        return 'up_to_date' if self._state_raw else 'update_available'

    @property
    def _state_raw(self):
        ''' The raw (True/False) format of the state. True is up-to-date '''
        return self.versions['newest_sha'] and \
            self.versions['current_sha'] == self.versions['newest_sha']

    @property
    def state_attributes(self):
        ''' current entity state attributes '''
        return {'local_sha': self.versions['current_sha'],
                'remote_sha': self.versions['newest_sha'],
                'message': self.versions['newest_msg'],
                'date': self.versions['newest_date'],
                'link': self.versions['newest_url']}
