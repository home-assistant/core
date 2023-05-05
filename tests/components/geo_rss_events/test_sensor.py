"""The test for the geo rss events sensor platform."""
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components import sensor
import homeassistant.components.geo_rss_events.sensor as geo_rss_events
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    EVENT_HOMEASSISTANT_START,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import assert_setup_component, async_fire_time_changed

URL = "http://geo.rss.local/geo_rss_events.xml"
VALID_CONFIG_WITH_CATEGORIES = {
    sensor.DOMAIN: [
        {
            "platform": "geo_rss_events",
            geo_rss_events.CONF_URL: URL,
            geo_rss_events.CONF_CATEGORIES: ["Category 1"],
        }
    ]
}
VALID_CONFIG = {
    sensor.DOMAIN: [{"platform": "geo_rss_events", geo_rss_events.CONF_URL: URL}]
}

"""Test the GeoRss service updater."""


@pytest.fixture
def mock_feed():
    """Pytest fixture for homeassistant.components.geo_rss_events.sensor.GenericFeed."""
    with patch(
        "homeassistant.components.geo_rss_events.sensor.GenericFeed"
    ) as mock_feed:
        yield mock_feed


def _generate_mock_feed_entry(
    external_id, title, distance_to_home, coordinates, category
):
    """Construct a mock feed entry for testing purposes."""
    feed_entry = MagicMock()
    feed_entry.external_id = external_id
    feed_entry.title = title
    feed_entry.distance_to_home = distance_to_home
    feed_entry.coordinates = coordinates
    feed_entry.category = category
    return feed_entry


async def test_setup(hass: HomeAssistant, mock_feed) -> None:
    """Test the general setup of the platform."""
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry(
        "1234", "Title 1", 15.5, (-31.0, 150.0), "Category 1"
    )
    mock_entry_2 = _generate_mock_feed_entry(
        "2345", "Title 2", 20.5, (-31.1, 150.1), "Category 1"
    )
    mock_feed.return_value.update.return_value = "OK", [mock_entry_1, mock_entry_2]

    utcnow = dt_util.utcnow()
    # Patching 'utcnow' to gain more control over the timed update.
    with patch(
        "homeassistant.util.dt.utcnow", return_value=utcnow
    ), assert_setup_component(1, sensor.DOMAIN):
        assert await async_setup_component(hass, sensor.DOMAIN, VALID_CONFIG)
        # Artificially trigger update.
        hass.bus.fire(EVENT_HOMEASSISTANT_START)
        # Collect events.
        await hass.async_block_till_done()

        all_states = hass.states.async_all()
        assert len(all_states) == 1

        state = hass.states.get("sensor.event_service_any")
        assert state is not None
        assert state.name == "Event Service Any"
        assert int(state.state) == 2
        assert state.attributes == {
            ATTR_FRIENDLY_NAME: "Event Service Any",
            ATTR_UNIT_OF_MEASUREMENT: "Events",
            ATTR_ICON: "mdi:alert",
            "Title 1": "16km",
            "Title 2": "20km",
        }

        # Simulate an update - empty data, but successful update,
        # so no changes to entities.
        mock_feed.return_value.update.return_value = "OK_NO_DATA", None
        async_fire_time_changed(hass, utcnow + geo_rss_events.SCAN_INTERVAL)
        await hass.async_block_till_done()

        all_states = hass.states.async_all()
        assert len(all_states) == 1
        state = hass.states.get("sensor.event_service_any")
        assert int(state.state) == 2

        # Simulate an update - empty data, removes all entities
        mock_feed.return_value.update.return_value = "ERROR", None
        async_fire_time_changed(hass, utcnow + 2 * geo_rss_events.SCAN_INTERVAL)
        await hass.async_block_till_done()

        all_states = hass.states.async_all()
        assert len(all_states) == 1
        state = hass.states.get("sensor.event_service_any")
        assert int(state.state) == 0
        assert state.attributes == {
            ATTR_FRIENDLY_NAME: "Event Service Any",
            ATTR_UNIT_OF_MEASUREMENT: "Events",
            ATTR_ICON: "mdi:alert",
        }


async def test_setup_with_categories(hass: HomeAssistant, mock_feed) -> None:
    """Test the general setup of the platform."""
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry(
        "1234", "Title 1", 15.5, (-31.0, 150.0), "Category 1"
    )
    mock_entry_2 = _generate_mock_feed_entry(
        "2345", "Title 2", 20.5, (-31.1, 150.1), "Category 1"
    )
    mock_feed.return_value.update.return_value = "OK", [mock_entry_1, mock_entry_2]

    with assert_setup_component(1, sensor.DOMAIN):
        assert await async_setup_component(
            hass, sensor.DOMAIN, VALID_CONFIG_WITH_CATEGORIES
        )
        # Artificially trigger update.
        hass.bus.fire(EVENT_HOMEASSISTANT_START)
        # Collect events.
        await hass.async_block_till_done()

        all_states = hass.states.async_all()
        assert len(all_states) == 1

        state = hass.states.get("sensor.event_service_category_1")
        assert state is not None
        assert state.name == "Event Service Category 1"
        assert int(state.state) == 2
        assert state.attributes == {
            ATTR_FRIENDLY_NAME: "Event Service Category 1",
            ATTR_UNIT_OF_MEASUREMENT: "Events",
            ATTR_ICON: "mdi:alert",
            "Title 1": "16km",
            "Title 2": "20km",
        }
