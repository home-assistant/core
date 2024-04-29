"""Component providing HA sensor support for Travis CI framework."""

from __future__ import annotations

from datetime import timedelta
import logging

from travispy import TravisPy
from travispy.errors import TravisError
import voluptuous as vol

from homeassistant.components import persistent_notification
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_MONITORED_CONDITIONS,
    CONF_SCAN_INTERVAL,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_BRANCH = "branch"
CONF_REPOSITORY = "repository"

DEFAULT_BRANCH_NAME = "master"

SCAN_INTERVAL = timedelta(seconds=30)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="last_build_id",
        name="Last Build ID",
        icon="mdi:card-account-details",
    ),
    SensorEntityDescription(
        key="last_build_duration",
        name="Last Build Duration",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        icon="mdi:timelapse",
    ),
    SensorEntityDescription(
        key="last_build_finished_at",
        name="Last Build Finished At",
        icon="mdi:timetable",
    ),
    SensorEntityDescription(
        key="last_build_started_at",
        name="Last Build Started At",
        icon="mdi:timetable",
    ),
    SensorEntityDescription(
        key="last_build_state",
        name="Last Build State",
        icon="mdi:github",
    ),
    SensorEntityDescription(
        key="state",
        name="State",
        icon="mdi:github",
    ),
)

SENSOR_KEYS: list[str] = [desc.key for desc in SENSOR_TYPES]

NOTIFICATION_ID = "travisci"
NOTIFICATION_TITLE = "Travis CI Sensor Setup"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_MONITORED_CONDITIONS, default=SENSOR_KEYS): vol.All(
            cv.ensure_list, [vol.In(SENSOR_KEYS)]
        ),
        vol.Required(CONF_BRANCH, default=DEFAULT_BRANCH_NAME): cv.string,
        vol.Optional(CONF_REPOSITORY, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Travis CI sensor."""

    token = config[CONF_API_KEY]
    repositories = config[CONF_REPOSITORY]
    branch = config[CONF_BRANCH]

    try:
        travis = TravisPy.github_auth(token)
        user = travis.user()

    except TravisError as ex:
        _LOGGER.error("Unable to connect to Travis CI service: %s", str(ex))
        persistent_notification.create(
            hass,
            f"Error: {ex}<br />You will need to restart hass after fixing.",
            title=NOTIFICATION_TITLE,
            notification_id=NOTIFICATION_ID,
        )
        return

    # non specific repository selected, then show all associated
    if not repositories:
        all_repos = travis.repos(member=user.login)
        repositories = [repo.slug for repo in all_repos]

    entities = []
    monitored_conditions = config[CONF_MONITORED_CONDITIONS]
    for repo in repositories:
        if "/" not in repo:
            repo = f"{user.login}/{repo}"

        entities.extend(
            [
                TravisCISensor(travis, repo, user, branch, description)
                for description in SENSOR_TYPES
                if description.key in monitored_conditions
            ]
        )

    add_entities(entities, True)


class TravisCISensor(SensorEntity):
    """Representation of a Travis CI sensor."""

    _attr_attribution = "Information provided by https://travis-ci.org/"

    def __init__(
        self, data, repo_name, user, branch, description: SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._build = None
        self._data = data
        self._repo_name = repo_name
        self._user = user
        self._branch = branch

        self._attr_name = f"{repo_name} {description.name}"

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attrs = {}

        if self._build and self._attr_native_value is not None:
            if self._user and self.entity_description.key == "state":
                attrs["Owner Name"] = self._user.name
                attrs["Owner Email"] = self._user.email
            else:
                attrs["Committer Name"] = self._build.commit.committer_name
                attrs["Committer Email"] = self._build.commit.committer_email
                attrs["Commit Branch"] = self._build.commit.branch
                attrs["Committed Date"] = self._build.commit.committed_at
                attrs["Commit SHA"] = self._build.commit.sha

        return attrs

    def update(self) -> None:
        """Get the latest data and updates the states."""
        _LOGGER.debug("Updating sensor %s", self.name)

        repo = self._data.repo(self._repo_name)
        self._build = self._data.build(repo.last_build_id)

        if self._build:
            if (sensor_type := self.entity_description.key) == "state":
                branch_stats = self._data.branch(self._branch, self._repo_name)
                self._attr_native_value = branch_stats.state

            else:
                param = sensor_type.replace("last_build_", "")
                self._attr_native_value = getattr(self._build, param)
