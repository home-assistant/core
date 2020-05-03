"""The tests for the USGS Earthquake Hazards Program Feed platform."""
import datetime

from homeassistant.components import geo_location
from homeassistant.components.geo_location import ATTR_SOURCE
from homeassistant.components.usgs_earthquakes_feed.geo_location import (
    ATTR_ALERT,
    ATTR_EXTERNAL_ID,
    ATTR_MAGNITUDE,
    ATTR_PLACE,
    ATTR_STATUS,
    ATTR_TIME,
    ATTR_TYPE,
    ATTR_UPDATED,
    CONF_FEED_TYPE,
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
    LENGTH_KILOMETERS,
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import MagicMock, call, patch
from tests.common import assert_setup_component, async_fire_time_changed

CONFIG = {
    geo_location.DOMAIN: [
        {
            "platform": "usgs_earthquakes_feed",
            CONF_FEED_TYPE: "past_hour_m25_earthquakes",
            CONF_RADIUS: 200,
        }
    ]
}

CONFIG_WITH_CUSTOM_LOCATION = {
    geo_location.DOMAIN: [
        {
            "platform": "usgs_earthquakes_feed",
            CONF_FEED_TYPE: "past_hour_m25_earthquakes",
            CONF_RADIUS: 200,
            CONF_LATITUDE: 15.1,
            CONF_LONGITUDE: 25.2,
        }
    ]
}


def _generate_mock_feed_entry(
    external_id,
    title,
    distance_to_home,
    coordinates,
    place=None,
    attribution=None,
    time=None,
    updated=None,
    magnitude=None,
    status=None,
    entry_type=None,
    alert=None,
):
    """Construct a mock feed entry for testing purposes."""
    feed_entry = MagicMock()
    feed_entry.external_id = external_id
    feed_entry.title = title
    feed_entry.distance_to_home = distance_to_home
    feed_entry.coordinates = coordinates
    feed_entry.place = place
    feed_entry.attribution = attribution
    feed_entry.time = time
    feed_entry.updated = updated
    feed_entry.magnitude = magnitude
    feed_entry.status = status
    feed_entry.type = entry_type
    feed_entry.alert = alert
    return feed_entry


async def test_setup(hass):
    """Test the general setup of the platform."""
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry(
        "1234",
        "Title 1",
        15.5,
        (-31.0, 150.0),
        place="Location 1",
        attribution="Attribution 1",
        time=datetime.datetime(2018, 9, 22, 8, 0, tzinfo=datetime.timezone.utc),
        updated=datetime.datetime(2018, 9, 22, 9, 0, tzinfo=datetime.timezone.utc),
        magnitude=5.7,
        status="Status 1",
        entry_type="Type 1",
        alert="Alert 1",
    )
    mock_entry_2 = _generate_mock_feed_entry("2345", "Title 2", 20.5, (-31.1, 150.1))
    mock_entry_3 = _generate_mock_feed_entry("3456", "Title 3", 25.5, (-31.2, 150.2))
    mock_entry_4 = _generate_mock_feed_entry("4567", "Title 4", 12.5, (-31.3, 150.3))

    # Patching 'utcnow' to gain more control over the timed update.
    utcnow = dt_util.utcnow()
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow), patch(
        "geojson_client.usgs_earthquake_hazards_program_feed."
        "UsgsEarthquakeHazardsProgramFeed"
    ) as mock_feed:
        mock_feed.return_value.update.return_value = (
            "OK",
            [mock_entry_1, mock_entry_2, mock_entry_3],
        )
        with assert_setup_component(1, geo_location.DOMAIN):
            assert await async_setup_component(hass, geo_location.DOMAIN, CONFIG)
            # Artificially trigger update.
            hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
            # Collect events.
            await hass.async_block_till_done()

            all_states = hass.states.async_all()
            assert len(all_states) == 3

            state = hass.states.get("geo_location.title_1")
            assert state is not None
            assert state.name == "Title 1"
            assert state.attributes == {
                ATTR_EXTERNAL_ID: "1234",
                ATTR_LATITUDE: -31.0,
                ATTR_LONGITUDE: 150.0,
                ATTR_FRIENDLY_NAME: "Title 1",
                ATTR_PLACE: "Location 1",
                ATTR_ATTRIBUTION: "Attribution 1",
                ATTR_TIME: datetime.datetime(
                    2018, 9, 22, 8, 0, tzinfo=datetime.timezone.utc
                ),
                ATTR_UPDATED: datetime.datetime(
                    2018, 9, 22, 9, 0, tzinfo=datetime.timezone.utc
                ),
                ATTR_STATUS: "Status 1",
                ATTR_TYPE: "Type 1",
                ATTR_ALERT: "Alert 1",
                ATTR_MAGNITUDE: 5.7,
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
                ATTR_SOURCE: "usgs_earthquakes_feed",
                ATTR_ICON: "mdi:pulse",
            }
            assert round(abs(float(state.state) - 15.5), 7) == 0

            state = hass.states.get("geo_location.title_2")
            assert state is not None
            assert state.name == "Title 2"
            assert state.attributes == {
                ATTR_EXTERNAL_ID: "2345",
                ATTR_LATITUDE: -31.1,
                ATTR_LONGITUDE: 150.1,
                ATTR_FRIENDLY_NAME: "Title 2",
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
                ATTR_SOURCE: "usgs_earthquakes_feed",
                ATTR_ICON: "mdi:pulse",
            }
            assert round(abs(float(state.state) - 20.5), 7) == 0

            state = hass.states.get("geo_location.title_3")
            assert state is not None
            assert state.name == "Title 3"
            assert state.attributes == {
                ATTR_EXTERNAL_ID: "3456",
                ATTR_LATITUDE: -31.2,
                ATTR_LONGITUDE: 150.2,
                ATTR_FRIENDLY_NAME: "Title 3",
                ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
                ATTR_SOURCE: "usgs_earthquakes_feed",
                ATTR_ICON: "mdi:pulse",
            }
            assert round(abs(float(state.state) - 25.5), 7) == 0

            # Simulate an update - one existing, one new entry,
            # one outdated entry
            mock_feed.return_value.update.return_value = (
                "OK",
                [mock_entry_1, mock_entry_4, mock_entry_3],
            )
            async_fire_time_changed(hass, utcnow + SCAN_INTERVAL)
            await hass.async_block_till_done()

            all_states = hass.states.async_all()
            assert len(all_states) == 3

            # Simulate an update - empty data, but successful update,
            # so no changes to entities.
            mock_feed.return_value.update.return_value = "OK_NO_DATA", None
            async_fire_time_changed(hass, utcnow + 2 * SCAN_INTERVAL)
            await hass.async_block_till_done()

            all_states = hass.states.async_all()
            assert len(all_states) == 3

            # Simulate an update - empty data, removes all entities
            mock_feed.return_value.update.return_value = "ERROR", None
            async_fire_time_changed(hass, utcnow + 3 * SCAN_INTERVAL)
            await hass.async_block_till_done()

            all_states = hass.states.async_all()
            assert len(all_states) == 0


async def test_setup_with_custom_location(hass):
    """Test the setup with a custom location."""
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry("1234", "Title 1", 20.5, (-31.1, 150.1))

    with patch(
        "geojson_client.usgs_earthquake_hazards_program_feed."
        "UsgsEarthquakeHazardsProgramFeed"
    ) as mock_feed:
        mock_feed.return_value.update.return_value = "OK", [mock_entry_1]

        with assert_setup_component(1, geo_location.DOMAIN):
            assert await async_setup_component(
                hass, geo_location.DOMAIN, CONFIG_WITH_CUSTOM_LOCATION
            )

            # Artificially trigger update.
            hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
            # Collect events.
            await hass.async_block_till_done()

            all_states = hass.states.async_all()
            assert len(all_states) == 1

            assert mock_feed.call_args == call(
                (15.1, 25.2),
                "past_hour_m25_earthquakes",
                filter_minimum_magnitude=0.0,
                filter_radius=200.0,
            )
