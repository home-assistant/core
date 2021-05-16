"""The tests for the GeoNet NZ Volcano Feed integration."""
from unittest.mock import AsyncMock, patch

from homeassistant.components import geonetnz_volcano
from homeassistant.components.geo_location import ATTR_DISTANCE
from homeassistant.components.geonetnz_volcano import DEFAULT_SCAN_INTERVAL
from homeassistant.components.geonetnz_volcano.const import (
    ATTR_ACTIVITY,
    ATTR_EXTERNAL_ID,
    ATTR_HAZARDS,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_RADIUS,
    EVENT_HOMEASSISTANT_START,
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util
from homeassistant.util.unit_system import IMPERIAL_SYSTEM

from tests.common import async_fire_time_changed
from tests.components.geonetnz_volcano import _generate_mock_feed_entry

CONFIG = {geonetnz_volcano.DOMAIN: {CONF_RADIUS: 200}}


async def test_setup(hass, legacy_patchable_time):
    """Test the general setup of the integration."""
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry(
        "1234",
        "Title 1",
        1,
        15.5,
        (38.0, -3.0),
        attribution="Attribution 1",
        activity="Activity 1",
        hazards="Hazards 1",
    )
    mock_entry_2 = _generate_mock_feed_entry("2345", "Title 2", 0, 20.5, (38.1, -3.1))
    mock_entry_3 = _generate_mock_feed_entry("3456", "Title 3", 2, 25.5, (38.2, -3.2))
    mock_entry_4 = _generate_mock_feed_entry("4567", "Title 4", 1, 12.5, (38.3, -3.3))

    # Patching 'utcnow' to gain more control over the timed update.
    utcnow = dt_util.utcnow()
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow), patch(
        "aio_geojson_client.feed.GeoJsonFeed.update", new_callable=AsyncMock
    ) as mock_feed_update:
        mock_feed_update.return_value = "OK", [mock_entry_1, mock_entry_2, mock_entry_3]
        assert await async_setup_component(hass, geonetnz_volcano.DOMAIN, CONFIG)
        # Artificially trigger update and collect events.
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        all_states = hass.states.async_all()
        # 3 sensor entities
        assert len(all_states) == 3

        state = hass.states.get("sensor.volcano_title_1")
        assert state is not None
        assert state.name == "Volcano Title 1"
        assert int(state.state) == 1
        assert state.attributes[ATTR_EXTERNAL_ID] == "1234"
        assert state.attributes[ATTR_LATITUDE] == 38.0
        assert state.attributes[ATTR_LONGITUDE] == -3.0
        assert state.attributes[ATTR_DISTANCE] == 15.5
        assert state.attributes[ATTR_FRIENDLY_NAME] == "Volcano Title 1"
        assert state.attributes[ATTR_ATTRIBUTION] == "Attribution 1"
        assert state.attributes[ATTR_ACTIVITY] == "Activity 1"
        assert state.attributes[ATTR_HAZARDS] == "Hazards 1"
        assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "alert level"
        assert state.attributes[ATTR_ICON] == "mdi:image-filter-hdr"

        state = hass.states.get("sensor.volcano_title_2")
        assert state is not None
        assert state.name == "Volcano Title 2"
        assert int(state.state) == 0
        assert state.attributes[ATTR_EXTERNAL_ID] == "2345"
        assert state.attributes[ATTR_LATITUDE] == 38.1
        assert state.attributes[ATTR_LONGITUDE] == -3.1
        assert state.attributes[ATTR_DISTANCE] == 20.5
        assert state.attributes[ATTR_FRIENDLY_NAME] == "Volcano Title 2"

        state = hass.states.get("sensor.volcano_title_3")
        assert state is not None
        assert state.name == "Volcano Title 3"
        assert int(state.state) == 2
        assert state.attributes[ATTR_EXTERNAL_ID] == "3456"
        assert state.attributes[ATTR_LATITUDE] == 38.2
        assert state.attributes[ATTR_LONGITUDE] == -3.2
        assert state.attributes[ATTR_DISTANCE] == 25.5
        assert state.attributes[ATTR_FRIENDLY_NAME] == "Volcano Title 3"

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

        # Simulate an update - empty data, keep all entities
        mock_feed_update.return_value = "ERROR", None
        async_fire_time_changed(hass, utcnow + 3 * DEFAULT_SCAN_INTERVAL)
        await hass.async_block_till_done()

        all_states = hass.states.async_all()
        assert len(all_states) == 4

        # Simulate an update - regular data for 3 entries
        mock_feed_update.return_value = "OK", [mock_entry_1, mock_entry_2, mock_entry_3]
        async_fire_time_changed(hass, utcnow + 4 * DEFAULT_SCAN_INTERVAL)
        await hass.async_block_till_done()

        all_states = hass.states.async_all()
        assert len(all_states) == 4


async def test_setup_imperial(hass):
    """Test the setup of the integration using imperial unit system."""
    hass.config.units = IMPERIAL_SYSTEM
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry("1234", "Title 1", 1, 15.5, (38.0, -3.0))

    # Patching 'utcnow' to gain more control over the timed update.
    utcnow = dt_util.utcnow()
    with patch("homeassistant.util.dt.utcnow", return_value=utcnow), patch(
        "aio_geojson_client.feed.GeoJsonFeed.update", new_callable=AsyncMock
    ) as mock_feed_update, patch(
        "aio_geojson_client.feed.GeoJsonFeed.__init__"
    ) as mock_feed_init:
        mock_feed_update.return_value = "OK", [mock_entry_1]
        assert await async_setup_component(hass, geonetnz_volcano.DOMAIN, CONFIG)
        # Artificially trigger update and collect events.
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        all_states = hass.states.async_all()
        assert len(all_states) == 1

        # Test conversion of 200 miles to kilometers.
        assert mock_feed_init.call_args[1].get("filter_radius") == 321.8688

        state = hass.states.get("sensor.volcano_title_1")
        assert state is not None
        assert state.name == "Volcano Title 1"
        assert int(state.state) == 1
        assert state.attributes[ATTR_EXTERNAL_ID] == "1234"
        assert state.attributes[ATTR_LATITUDE] == 38.0
        assert state.attributes[ATTR_LONGITUDE] == -3.0
        assert state.attributes[ATTR_DISTANCE] == 9.6
        assert state.attributes[ATTR_FRIENDLY_NAME] == "Volcano Title 1"
        assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "alert level"
        assert state.attributes[ATTR_ICON] == "mdi:image-filter-hdr"
