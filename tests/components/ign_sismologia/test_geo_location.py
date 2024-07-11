"""The tests for the IGN Sismologia (Earthquakes) Feed platform."""

import datetime
from unittest.mock import MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
from georss_ign_sismologia_client import IgnSismologiaFeed

from homeassistant.components import geo_location
from homeassistant.components.geo_location import ATTR_SOURCE
from homeassistant.components.ign_sismologia.geo_location import (
    ATTR_EXTERNAL_ID,
    ATTR_IMAGE_URL,
    ATTR_MAGNITUDE,
    ATTR_PUBLICATION_DATE,
    ATTR_REGION,
    ATTR_TITLE,
    SCAN_INTERVAL,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    EVENT_HOMEASSISTANT_START,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import assert_setup_component, async_fire_time_changed

CONFIG = {geo_location.DOMAIN: [{"platform": "ign_sismologia", CONF_RADIUS: 200}]}

CONFIG_WITH_CUSTOM_LOCATION = {
    geo_location.DOMAIN: [
        {
            "platform": "ign_sismologia",
            CONF_RADIUS: 200,
            CONF_LATITUDE: 40.4,
            CONF_LONGITUDE: -3.7,
        }
    ]
}


def _generate_mock_feed_entry(
    external_id,
    title,
    distance_to_home,
    coordinates,
    region=None,
    attribution=None,
    published=None,
    magnitude=None,
    image_url=None,
):
    """Construct a mock feed entry for testing purposes."""
    feed_entry = MagicMock()
    feed_entry.external_id = external_id
    feed_entry.title = title
    feed_entry.distance_to_home = distance_to_home
    feed_entry.coordinates = coordinates
    feed_entry.region = region
    feed_entry.attribution = attribution
    feed_entry.published = published
    feed_entry.magnitude = magnitude
    feed_entry.image_url = image_url
    return feed_entry


async def test_setup(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test the general setup of the platform."""
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry(
        "1234",
        "Title 1",
        15.5,
        (38.0, -3.0),
        region="Region 1",
        attribution="Attribution 1",
        published=datetime.datetime(2018, 9, 22, 8, 0, tzinfo=datetime.UTC),
        magnitude=5.7,
        image_url="http://image.url/map.jpg",
    )
    mock_entry_2 = _generate_mock_feed_entry(
        "2345", "Title 2", 20.5, (38.1, -3.1), magnitude=4.6
    )
    mock_entry_3 = _generate_mock_feed_entry(
        "3456", "Title 3", 25.5, (38.2, -3.2), region="Region 3"
    )
    mock_entry_4 = _generate_mock_feed_entry("4567", "Title 4", 12.5, (38.3, -3.3))

    utcnow = dt_util.utcnow()
    freezer.move_to(utcnow)

    with patch("georss_client.feed.GeoRssFeed.update") as mock_feed_update:
        mock_feed_update.return_value = (
            "OK",
            [mock_entry_1, mock_entry_2, mock_entry_3],
        )
        with assert_setup_component(1, geo_location.DOMAIN):
            assert await async_setup_component(hass, geo_location.DOMAIN, CONFIG)
            await hass.async_block_till_done()
            # Artificially trigger update.
            hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
            # Collect events.
            await hass.async_block_till_done()

            all_states = hass.states.async_all()
            assert len(all_states) == 3

            state = hass.states.get("geo_location.m_5_7_region_1")
            assert state is not None
            assert state.name == "M 5.7 - Region 1"
            assert state.attributes == {
                ATTR_EXTERNAL_ID: "1234",
                ATTR_LATITUDE: 38.0,
                ATTR_LONGITUDE: -3.0,
                ATTR_FRIENDLY_NAME: "M 5.7 - Region 1",
                ATTR_TITLE: "Title 1",
                ATTR_REGION: "Region 1",
                ATTR_ATTRIBUTION: "Attribution 1",
                ATTR_PUBLICATION_DATE: datetime.datetime(
                    2018, 9, 22, 8, 0, tzinfo=datetime.UTC
                ),
                ATTR_IMAGE_URL: "http://image.url/map.jpg",
                ATTR_MAGNITUDE: 5.7,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfLength.KILOMETERS,
                ATTR_SOURCE: "ign_sismologia",
                ATTR_ICON: "mdi:pulse",
            }
            assert float(state.state) == 15.5

            state = hass.states.get("geo_location.m_4_6")
            assert state is not None
            assert state.name == "M 4.6"
            assert state.attributes == {
                ATTR_EXTERNAL_ID: "2345",
                ATTR_LATITUDE: 38.1,
                ATTR_LONGITUDE: -3.1,
                ATTR_FRIENDLY_NAME: "M 4.6",
                ATTR_TITLE: "Title 2",
                ATTR_MAGNITUDE: 4.6,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfLength.KILOMETERS,
                ATTR_SOURCE: "ign_sismologia",
                ATTR_ICON: "mdi:pulse",
            }
            assert float(state.state) == 20.5

            state = hass.states.get("geo_location.region_3")
            assert state is not None
            assert state.name == "Region 3"
            assert state.attributes == {
                ATTR_EXTERNAL_ID: "3456",
                ATTR_LATITUDE: 38.2,
                ATTR_LONGITUDE: -3.2,
                ATTR_FRIENDLY_NAME: "Region 3",
                ATTR_TITLE: "Title 3",
                ATTR_REGION: "Region 3",
                ATTR_UNIT_OF_MEASUREMENT: UnitOfLength.KILOMETERS,
                ATTR_SOURCE: "ign_sismologia",
                ATTR_ICON: "mdi:pulse",
            }
            assert float(state.state) == 25.5

            # Simulate an update - one existing, one new entry,
            # one outdated entry
            mock_feed_update.return_value = (
                "OK",
                [mock_entry_1, mock_entry_4, mock_entry_3],
            )
            async_fire_time_changed(hass, utcnow + SCAN_INTERVAL)
            await hass.async_block_till_done(wait_background_tasks=True)

            all_states = hass.states.async_all()
            assert len(all_states) == 3

            # Simulate an update - empty data, but successful update,
            # so no changes to entities.
            mock_feed_update.return_value = "OK_NO_DATA", None
            async_fire_time_changed(hass, utcnow + 2 * SCAN_INTERVAL)
            await hass.async_block_till_done(wait_background_tasks=True)

            all_states = hass.states.async_all()
            assert len(all_states) == 3

            # Simulate an update - empty data, removes all entities
            mock_feed_update.return_value = "ERROR", None
            async_fire_time_changed(hass, utcnow + 3 * SCAN_INTERVAL)
            await hass.async_block_till_done(wait_background_tasks=True)

            all_states = hass.states.async_all()
            assert len(all_states) == 0


async def test_setup_with_custom_location(hass: HomeAssistant) -> None:
    """Test the setup with a custom location."""
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry("1234", "Title 1", 20.5, (38.1, -3.1))

    with (
        patch(
            "georss_ign_sismologia_client.feed_manager.IgnSismologiaFeed",
            wraps=IgnSismologiaFeed,
        ) as mock_feed,
        patch("georss_client.feed.GeoRssFeed.update") as mock_feed_update,
    ):
        mock_feed_update.return_value = "OK", [mock_entry_1]

        with assert_setup_component(1, geo_location.DOMAIN):
            assert await async_setup_component(
                hass, geo_location.DOMAIN, CONFIG_WITH_CUSTOM_LOCATION
            )
            await hass.async_block_till_done()

            # Artificially trigger update.
            hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
            # Collect events.
            await hass.async_block_till_done()

            all_states = hass.states.async_all()
            assert len(all_states) == 1

            assert mock_feed.call_args == call(
                (40.4, -3.7), filter_minimum_magnitude=0.0, filter_radius=200.0
            )
