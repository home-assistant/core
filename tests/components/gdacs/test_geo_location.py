"""The tests for the GDACS Feed integration."""
import datetime

from homeassistant.components import gdacs
from homeassistant.components.gdacs import DEFAULT_SCAN_INTERVAL, DOMAIN, FEED
from homeassistant.components.gdacs.geo_location import (
    ATTR_ALERT_LEVEL,
    ATTR_COUNTRY,
    ATTR_DESCRIPTION,
    ATTR_DURATION_IN_WEEK,
    ATTR_EVENT_TYPE,
    ATTR_EXTERNAL_ID,
    ATTR_FROM_DATE,
    ATTR_POPULATION,
    ATTR_SEVERITY,
    ATTR_TO_DATE,
    ATTR_VULNERABILITY,
)
from homeassistant.components.geo_location import ATTR_SOURCE
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_RADIUS,
    EVENT_HOMEASSISTANT_START,
    LENGTH_KILOMETERS,
)
from homeassistant.helpers.entity_registry import async_get_registry
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import IMPERIAL_SYSTEM

from tests.async_mock import patch
from tests.common import async_fire_time_changed
from tests.components.gdacs import _generate_mock_feed_entry

CONFIG = {gdacs.DOMAIN: {CONF_RADIUS: 200}}


async def test_setup(hass):
    """Test the general setup of the integration."""
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry(
        "1234",
        "Description 1",
        15.5,
        (38.0, -3.0),
        event_name="Name 1",
        event_type_short="DR",
        event_type="Drought",
        alert_level="Alert Level 1",
        country="Country 1",
        attribution="Attribution 1",
        from_date=datetime.datetime(2020, 1, 10, 8, 0, tzinfo=datetime.timezone.utc),
        to_date=datetime.datetime(2020, 1, 20, 8, 0, tzinfo=datetime.timezone.utc),
        duration_in_week=1,
        population="Population 1",
        severity="Severity 1",
        vulnerability="Vulnerability 1",
    )
    mock_entry_2 = _generate_mock_feed_entry(
        "2345",
        "Description 2",
        20.5,
        (38.1, -3.1),
        event_name="Name 2",
        event_type_short="TC",
        event_type="Tropical Cyclone",
    )
    mock_entry_3 = _generate_mock_feed_entry(
        "3456",
        "Description 3",
        25.5,
        (38.2, -3.2),
        event_name="Name 3",
        event_type_short="TC",
        event_type="Tropical Cyclone",
        country="Country 2",
    )
    mock_entry_4 = _generate_mock_feed_entry(
        "4567", "Description 4", 12.5, (38.3, -3.3)
    )

    # Patching 'utcnow' to gain more control over the timed update.
    utcnow = dt_util.utcnow()
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow), patch(
        "aio_georss_client.feed.GeoRssFeed.update"
    ) as mock_feed_update:
        mock_feed_update.return_value = "OK", [mock_entry_1, mock_entry_2, mock_entry_3]
        assert await async_setup_component(hass, gdacs.DOMAIN, CONFIG)
        # Artificially trigger update and collect events.
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        all_states = hass.states.async_all()
        # 3 geolocation and 1 sensor entities
        assert len(all_states) == 4
        entity_registry = await async_get_registry(hass)
        assert len(entity_registry.entities) == 4

        state = hass.states.get("geo_location.drought_name_1")
        assert state is not None
        assert state.name == "Drought: Name 1"
        assert state.attributes == {
            ATTR_EXTERNAL_ID: "1234",
            ATTR_LATITUDE: 38.0,
            ATTR_LONGITUDE: -3.0,
            ATTR_FRIENDLY_NAME: "Drought: Name 1",
            ATTR_DESCRIPTION: "Description 1",
            ATTR_COUNTRY: "Country 1",
            ATTR_ATTRIBUTION: "Attribution 1",
            ATTR_FROM_DATE: datetime.datetime(
                2020, 1, 10, 8, 0, tzinfo=datetime.timezone.utc
            ),
            ATTR_TO_DATE: datetime.datetime(
                2020, 1, 20, 8, 0, tzinfo=datetime.timezone.utc
            ),
            ATTR_DURATION_IN_WEEK: 1,
            ATTR_ALERT_LEVEL: "Alert Level 1",
            ATTR_POPULATION: "Population 1",
            ATTR_EVENT_TYPE: "Drought",
            ATTR_SEVERITY: "Severity 1",
            ATTR_VULNERABILITY: "Vulnerability 1",
            ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            ATTR_SOURCE: "gdacs",
            ATTR_ICON: "mdi:water-off",
        }
        assert float(state.state) == 15.5

        state = hass.states.get("geo_location.tropical_cyclone_name_2")
        assert state is not None
        assert state.name == "Tropical Cyclone: Name 2"
        assert state.attributes == {
            ATTR_EXTERNAL_ID: "2345",
            ATTR_LATITUDE: 38.1,
            ATTR_LONGITUDE: -3.1,
            ATTR_FRIENDLY_NAME: "Tropical Cyclone: Name 2",
            ATTR_DESCRIPTION: "Description 2",
            ATTR_EVENT_TYPE: "Tropical Cyclone",
            ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            ATTR_SOURCE: "gdacs",
            ATTR_ICON: "mdi:weather-hurricane",
        }
        assert float(state.state) == 20.5

        state = hass.states.get("geo_location.tropical_cyclone_name_3")
        assert state is not None
        assert state.name == "Tropical Cyclone: Name 3"
        assert state.attributes == {
            ATTR_EXTERNAL_ID: "3456",
            ATTR_LATITUDE: 38.2,
            ATTR_LONGITUDE: -3.2,
            ATTR_FRIENDLY_NAME: "Tropical Cyclone: Name 3",
            ATTR_DESCRIPTION: "Description 3",
            ATTR_EVENT_TYPE: "Tropical Cyclone",
            ATTR_COUNTRY: "Country 2",
            ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            ATTR_SOURCE: "gdacs",
            ATTR_ICON: "mdi:weather-hurricane",
        }
        assert float(state.state) == 25.5

        # Simulate an update - two existing, one new entry, one outdated entry
        mock_feed_update.return_value = "OK", [mock_entry_1, mock_entry_4, mock_entry_3]
        async_fire_time_changed(hass, utcnow + DEFAULT_SCAN_INTERVAL)
        await hass.async_block_till_done()

        all_states = hass.states.async_all()
        assert len(all_states) == 4

        # Simulate an update - empty data, but successful update,
        # so no changes to entities.
        mock_feed_update.return_value = "OK_NO_DATA", None
        async_fire_time_changed(hass, utcnow + 2 * DEFAULT_SCAN_INTERVAL)
        await hass.async_block_till_done()

        all_states = hass.states.async_all()
        assert len(all_states) == 4

        # Simulate an update - empty data, removes all entities
        mock_feed_update.return_value = "ERROR", None
        async_fire_time_changed(hass, utcnow + 3 * DEFAULT_SCAN_INTERVAL)
        await hass.async_block_till_done()

        all_states = hass.states.async_all()
        assert len(all_states) == 1
        assert len(entity_registry.entities) == 1


async def test_setup_imperial(hass):
    """Test the setup of the integration using imperial unit system."""
    hass.config.units = IMPERIAL_SYSTEM
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry(
        "1234",
        "Description 1",
        15.5,
        (38.0, -3.0),
        event_name="Name 1",
        event_type_short="DR",
        event_type="Drought",
    )

    # Patching 'utcnow' to gain more control over the timed update.
    utcnow = dt_util.utcnow()
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow), patch(
        "aio_georss_client.feed.GeoRssFeed.update"
    ) as mock_feed_update, patch(
        "aio_georss_client.feed.GeoRssFeed.last_timestamp", create=True
    ):
        mock_feed_update.return_value = "OK", [mock_entry_1]
        assert await async_setup_component(hass, gdacs.DOMAIN, CONFIG)
        # Artificially trigger update and collect events.
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        all_states = hass.states.async_all()
        assert len(all_states) == 2

        # Test conversion of 200 miles to kilometers.
        feeds = hass.data[DOMAIN][FEED]
        assert feeds is not None
        assert len(feeds) == 1
        manager = list(feeds.values())[0]
        # Ensure that the filter value in km is correctly set.
        assert manager._feed_manager._feed._filter_radius == 321.8688

        state = hass.states.get("geo_location.drought_name_1")
        assert state is not None
        assert state.name == "Drought: Name 1"
        assert state.attributes == {
            ATTR_EXTERNAL_ID: "1234",
            ATTR_LATITUDE: 38.0,
            ATTR_LONGITUDE: -3.0,
            ATTR_FRIENDLY_NAME: "Drought: Name 1",
            ATTR_DESCRIPTION: "Description 1",
            ATTR_EVENT_TYPE: "Drought",
            ATTR_UNIT_OF_MEASUREMENT: "mi",
            ATTR_SOURCE: "gdacs",
            ATTR_ICON: "mdi:water-off",
        }
        # 15.5km (as defined in mock entry) has been converted to 9.6mi.
        assert float(state.state) == 9.6
