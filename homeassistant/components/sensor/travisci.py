"""
This component provides HA sensor support for Travis CI framework.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.travisci/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_API_KEY, CONF_SCAN_INTERVAL,
    CONF_MONITORED_CONDITIONS, STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['TravisPy==0.3.5']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Information provided by https://travis-ci.org/"
CONF_BRANCH = 'branch'
CONF_REPOSITORY = 'repository'

DEFAULT_BRANCH_NAME = 'master'

SCAN_INTERVAL = timedelta(seconds=30)

# sensor_type [ description, unit, icon ]
SENSOR_TYPES = {
    'last_build_id': ['Last Build ID', '', 'mdi:account-card-details'],
    'last_build_duration': ['Last Build Duration', 'sec', 'mdi:timelapse'],
    'last_build_finished_at': ['Last Build Finished At', '', 'mdi:timetable'],
    'last_build_started_at': ['Last Build Started At', '', 'mdi:timetable'],
    'last_build_state': ['Last Build State', '', 'mdi:github-circle'],
    'state': ['State', '', 'mdi:github-circle'],

}

NOTIFICATION_ID = 'travisci'
NOTIFICATION_TITLE = 'Travis CI Sensor Setup'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Required(CONF_BRANCH, default=DEFAULT_BRANCH_NAME): cv.string,
    vol.Optional(CONF_REPOSITORY, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
        cv.time_period,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Travis CI sensor."""
    from travispy import TravisPy
    from travispy.errors import TravisError

    token = config.get(CONF_API_KEY)
    repositories = config.get(CONF_REPOSITORY)
    branch = config.get(CONF_BRANCH)

    try:
        travis = TravisPy.github_auth(token)
        user = travis.user()

    except TravisError as ex:
        _LOGGER.error("Unable to connect to Travis CI service: %s", str(ex))
        hass.components.persistent_notification.create(
            'Error: {}<br />'
            'You will need to restart hass after fixing.'
            ''.format(ex),
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID)
        return False

    sensors = []

    # non specificy repository selected, then show all associated
    if not repositories:
        all_repos = travis.repos(member=user.login)
        repositories = [repo.slug for repo in all_repos]

    for repo in repositories:
        if '/' not in repo:
            repo = "{0}/{1}".format(user.login, repo)

        for sensor_type in config.get(CONF_MONITORED_CONDITIONS):
            sensors.append(
                TravisCISensor(travis, repo, user, branch, sensor_type))

    add_devices(sensors, True)
    return True


class TravisCISensor(Entity):
    """Representation of a Travis CI sensor."""

    def __init__(self, data, repo_name, user, branch, sensor_type):
        """Initialize the sensor."""
        self._build = None
        self._sensor_type = sensor_type
        self._data = data
        self._repo_name = repo_name
        self._user = user
        self._branch = branch
        self._state = STATE_UNKNOWN
        self._name = "{0} {1}".format(self._repo_name,
                                      SENSOR_TYPES[self._sensor_type][0])

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return SENSOR_TYPES[self._sensor_type][1]

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attrs = {}
        attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION

        if self._build and self._state is not STATE_UNKNOWN:
            if self._user and self._sensor_type == 'state':
                attrs['Owner Name'] = self._user.name
                attrs['Owner Email'] = self._user.email
            else:
                attrs['Committer Name'] = self._build.commit.committer_name
                attrs['Committer Email'] = self._build.commit.committer_email
                attrs['Commit Branch'] = self._build.commit.branch
                attrs['Committed Date'] = self._build.commit.committed_at
                attrs['Commit SHA'] = self._build.commit.sha

        return attrs

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return SENSOR_TYPES[self._sensor_type][2]

    def update(self):
        """Get the latest data and updates the states."""
        _LOGGER.debug("Updating sensor %s", self._name)

        repo = self._data.repo(self._repo_name)
        self._build = self._data.build(repo.last_build_id)

        if self._build:
            if self._sensor_type == 'state':
                branch_stats = \
                    self._data.branch(self._branch, self._repo_name)
                self._state = branch_stats.state

            else:
                param = self._sensor_type.replace('last_build_', '')
                self._state = getattr(self._build, param)
