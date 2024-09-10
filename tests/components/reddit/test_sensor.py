"""The tests for the Reddit platform."""

import copy
from unittest.mock import patch

from homeassistant.components.reddit.sensor import (
    ATTR_BODY,
    ATTR_COMMENTS_NUMBER,
    ATTR_CREATED,
    ATTR_ID,
    ATTR_POSTS,
    ATTR_SCORE,
    ATTR_SUBREDDIT,
    ATTR_TITLE,
    ATTR_URL,
    CONF_SORT_BY,
    DOMAIN,
)
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_MAXIMUM,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

VALID_CONFIG = {
    "sensor": {
        "platform": DOMAIN,
        CONF_CLIENT_ID: "test_client_id",
        CONF_CLIENT_SECRET: "test_client_secret",
        CONF_USERNAME: "test_username",
        CONF_PASSWORD: "test_password",
        "subreddits": ["worldnews", "news"],
    }
}

VALID_LIMITED_CONFIG = {
    "sensor": {
        "platform": DOMAIN,
        CONF_CLIENT_ID: "test_client_id",
        CONF_CLIENT_SECRET: "test_client_secret",
        CONF_USERNAME: "test_username",
        CONF_PASSWORD: "test_password",
        "subreddits": ["worldnews", "news"],
        CONF_MAXIMUM: 1,
    }
}


INVALID_SORT_BY_CONFIG = {
    "sensor": {
        "platform": DOMAIN,
        CONF_CLIENT_ID: "test_client_id",
        CONF_CLIENT_SECRET: "test_client_secret",
        CONF_USERNAME: "test_username",
        CONF_PASSWORD: "test_password",
        "subreddits": ["worldnews", "news"],
        "sort_by": "invalid_sort_by",
    }
}


class ObjectView:
    """Use dict properties as attributes."""

    def __init__(self, d) -> None:
        """Set dict as internal dict."""
        self.__dict__ = d


MOCK_RESULTS = {
    "results": [
        ObjectView(
            {
                "id": 0,
                "url": "http://example.com/1",
                "title": "example1",
                "score": "1",
                "num_comments": "1",
                "created": "",
                "selftext": "example1 selftext",
            }
        ),
        ObjectView(
            {
                "id": 1,
                "url": "http://example.com/2",
                "title": "example2",
                "score": "2",
                "num_comments": "2",
                "created": "",
                "selftext": "example2 selftext",
            }
        ),
    ]
}

MOCK_RESULTS_LENGTH = len(MOCK_RESULTS["results"])


class MockPraw:
    """Mock class for Reddit library."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        username: str,
        password: str,
        user_agent: str,
    ) -> None:
        """Add mock data for API return."""
        self._data = MOCK_RESULTS

    def subreddit(self, subreddit: str):
        """Return an instance of a subreddit."""
        return MockSubreddit(subreddit, self._data)


class MockSubreddit:
    """Mock class for a subreddit instance."""

    def __init__(self, subreddit: str, data) -> None:
        """Add mock data for API return."""
        self._subreddit = subreddit
        self._data = data

    def top(self, limit):
        """Return top posts for a subreddit."""
        return self._return_data(limit)

    def controversial(self, limit):
        """Return controversial posts for a subreddit."""
        return self._return_data(limit)

    def hot(self, limit):
        """Return hot posts for a subreddit."""
        return self._return_data(limit)

    def new(self, limit):
        """Return new posts for a subreddit."""
        return self._return_data(limit)

    def _return_data(self, limit):
        """Test method to return modified data."""
        data = copy.deepcopy(self._data)
        return data["results"][:limit]


@patch("praw.Reddit", new=MockPraw)
async def test_setup_with_valid_config(hass: HomeAssistant) -> None:
    """Test the platform setup with Reddit configuration."""
    assert await async_setup_component(hass, "sensor", VALID_CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.reddit_worldnews")
    assert int(state.state) == MOCK_RESULTS_LENGTH

    state = hass.states.get("sensor.reddit_news")
    assert int(state.state) == MOCK_RESULTS_LENGTH

    assert state.attributes[ATTR_SUBREDDIT] == "news"

    assert state.attributes[ATTR_POSTS][0] == {
        ATTR_ID: 0,
        ATTR_URL: "http://example.com/1",
        ATTR_TITLE: "example1",
        ATTR_SCORE: "1",
        ATTR_COMMENTS_NUMBER: "1",
        ATTR_CREATED: "",
        ATTR_BODY: "example1 selftext",
    }

    assert state.attributes[CONF_SORT_BY] == "hot"


@patch("praw.Reddit", new=MockPraw)
async def test_setup_with_invalid_config(hass: HomeAssistant) -> None:
    """Test the platform setup with invalid Reddit configuration."""
    assert await async_setup_component(hass, "sensor", INVALID_SORT_BY_CONFIG)
    await hass.async_block_till_done()
    assert not hass.states.get("sensor.reddit_worldnews")
