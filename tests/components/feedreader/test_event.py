"""The tests for the feedreader event entity."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.feedreader.const import DOMAIN
from homeassistant.components.feedreader.event import (
    ATTR_CONTENT,
    ATTR_LINK,
    ATTR_TITLE,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .const import VALID_CONFIG_DEFAULT

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_event_entity(
    hass: HomeAssistant, feed_one_event, feed_two_event
) -> None:
    """Test feed event entity."""
    entry = MockConfigEntry(domain=DOMAIN, data=VALID_CONFIG_DEFAULT)
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.feedreader.coordinator.feedparser.http.get",
        side_effect=[feed_one_event, feed_two_event],
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get("event.mock_title")
        assert state
        assert state.attributes[ATTR_TITLE] == "Title 1"
        assert state.attributes[ATTR_LINK] == "http://www.example.com/link/1"
        assert state.attributes[ATTR_CONTENT] == [
            {
                "type": "text/plain",
                "language": None,
                "base": "",
                "value": "Content 1",
            }
        ]

        future = dt_util.utcnow() + timedelta(hours=1, seconds=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done(wait_background_tasks=True)

        state = hass.states.get("event.mock_title")
        assert state
        assert state.attributes[ATTR_TITLE] == "Title 2"
        assert state.attributes[ATTR_LINK] == "http://www.example.com/link/2"
        assert state.attributes[ATTR_CONTENT] == [
            {
                "type": "text/plain",
                "language": None,
                "base": "",
                "value": "Content 2",
            }
        ]
