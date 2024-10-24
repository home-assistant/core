"""Support for Reddit."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any, Final

import praw
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import (
    ATTR_ID,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_MAXIMUM,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_SORT_BY = "sort_by"
CONF_SUBREDDITS = "subreddits"
CONF_REDDITORS = "redditors"

ATTR_BODY: Final = "body"
ATTR_COMMENTS_NUMBER: Final = "comms_num"
ATTR_CREATED: Final = "created"
ATTR_POSTS: Final = "posts"
ATTR_SUBREDDIT: Final = "subreddit"
ATTR_SCORE: Final = "score"
ATTR_TITLE: Final = "title"
ATTR_URL: Final = "url"
ATTR_REDDITOR: Final = "redditor"

DEFAULT_NAME = "Reddit"

DOMAIN = "reddit"

LIST_TYPES = ["top", "controversial", "hot", "new"]

SCAN_INTERVAL = timedelta(seconds=300)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_SUBREDDITS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_REDDITORS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_SORT_BY, default="hot"): vol.All(
            cv.string, vol.In(LIST_TYPES)
        ),
        vol.Optional(CONF_MAXIMUM, default=10): cv.positive_int,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Reddit sensor platform."""
    subreddits = config[CONF_SUBREDDITS]
    redditors = config.get(CONF_REDDITORS, [])
    user_agent = f"{config[CONF_USERNAME]}_home_assistant_sensor"
    limit = config[CONF_MAXIMUM]
    sort_by = config[CONF_SORT_BY]
    try:
        reddit = praw.Reddit(
            client_id=config[CONF_CLIENT_ID],
            client_secret=config[CONF_CLIENT_SECRET],
            username=config[CONF_USERNAME],
            password=config[CONF_PASSWORD],
            user_agent=user_agent,
        )

        _LOGGER.debug("Connected to praw")

    except praw.exceptions.PRAWException as err:
        _LOGGER.error("Reddit error %s", err)
        return

    sensors = [
        RedditSensor(reddit, subreddit, limit, sort_by, ATTR_SUBREDDIT)
        for subreddit in subreddits
    ]
    sensors.extend(
        RedditSensor(reddit, redditor, limit, sort_by, ATTR_REDDITOR)
        for redditor in redditors
    )

    add_entities(sensors, True)


class RedditSensor(SensorEntity):
    """Representation of a Reddit sensor."""

    def __init__(
        self,
        reddit,
        subreddit: str,
        limit: int,
        sort_by: str,
        mode: str,
    ) -> None:
        """Initialize the Reddit sensor."""
        self._reddit = reddit
        self._subreddit = subreddit
        self._limit = limit
        self._sort_by = sort_by
        self._mode = mode

        self._subreddit_data: list = []

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return (
            self._mode == ATTR_SUBREDDIT
            and f"reddit_{self._subreddit}"
            or f"reddit_user_{self._subreddit}"
        )

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return len(self._subreddit_data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            ATTR_SUBREDDIT: self._subreddit,
            ATTR_POSTS: self._subreddit_data,
            CONF_SORT_BY: self._sort_by,
        }

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        return "mdi:reddit"

    def update(self) -> None:
        """Update data from Reddit API."""
        self._subreddit_data = []

        try:
            if hasattr(self._reddit, self._mode):
                data_source = getattr(self._reddit, self._mode)(self._subreddit)
                if hasattr(data_source, self._sort_by):
                    method_to_call = getattr(data_source, self._sort_by)

                    for submission in method_to_call(limit=self._limit):
                        self._subreddit_data.append(
                            {
                                ATTR_ID: getattr(submission, "id", ""),
                                ATTR_URL: getattr(submission, "url", ""),
                                ATTR_TITLE: getattr(submission, "title", ""),
                                ATTR_SCORE: getattr(submission, "score", ""),
                                ATTR_COMMENTS_NUMBER: getattr(
                                    submission, "num_comments", ""
                                ),
                                ATTR_CREATED: getattr(submission, "created", ""),
                                ATTR_BODY: getattr(submission, "selftext", ""),
                            }
                        )

        except praw.exceptions.PRAWException as err:
            _LOGGER.error("Reddit error %s", err)
