"""Define tests for the GeoJSON Events general setup."""
from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time

from homeassistant.components.geo_json_events.const import (
    ATTR_EXTERNAL_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    FEED,
)
from homeassistant.components.geo_location import ATTR_SOURCE
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_RADIUS,
    CONF_URL,
    EVENT_HOMEASSISTANT_START,
    LENGTH_KILOMETERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import async_entries_for_config_entry
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.geo_json_events import _generate_mock_feed_entry

CONFIG = {
    DOMAIN: {CONF_URL: "http://geo.json.local/geo_json_events.json", CONF_RADIUS: 200}
}


async def test_component_unload_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that loading and unloading of a config entry works."""
    config_entry.add_to_hass(hass)
    with patch(
        "aio_geojson_generic_client.GenericFeedManager.update"
    ) as mock_feed_manager_update:
        # Load config entry.
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_feed_manager_update.call_count == 1
        assert hass.data[DOMAIN][FEED][config_entry.entry_id] is not None
        # Unload config entry.
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.data[DOMAIN][FEED].get(config_entry.entry_id) is None


async def test_entity_lifecycle(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test entity lifecycle.."""
    config_entry.add_to_hass(hass)
    # Set up a mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry("1234", "Title 1", 15.5, (-31.0, 150.0))
    mock_entry_2 = _generate_mock_feed_entry("2345", "Title 2", 20.5, (-31.1, 150.1))
    mock_entry_3 = _generate_mock_feed_entry("3456", "Title 3", 25.5, (-31.2, 150.2))
    mock_entry_4 = _generate_mock_feed_entry("4567", "Title 4", 12.5, (-31.3, 150.3))

    utcnow = dt_util.utcnow()
    with freeze_time(utcnow), patch(
        "aio_geojson_client.feed.GeoJsonFeed.update"
    ) as mock_feed_update:
        mock_feed_update.return_value = "OK", [mock_entry_1, mock_entry_2, mock_entry_3]

        # Load config entry.
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # assert await async_setup_component(hass, DOMAIN, CONFIG)
        # await hass.async_block_till_done()
        # Artificially trigger update and collect events.
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        # 3 geolocation and 1 sensor entities
        assert len(hass.states.async_entity_ids("geo_location")) == 3
        entity_registry = er.async_get(hass)
        assert len(entity_registry.entities) == 3

        state = hass.states.get("geo_location.title_1")
        assert state is not None
        assert state.name == "Title 1"
        assert state.attributes == {
            ATTR_EXTERNAL_ID: "1234",
            ATTR_LATITUDE: -31.0,
            ATTR_LONGITUDE: 150.0,
            ATTR_FRIENDLY_NAME: "Title 1",
            ATTR_UNIT_OF_MEASUREMENT: LENGTH_KILOMETERS,
            ATTR_SOURCE: "geo_json_events",
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
            ATTR_SOURCE: "geo_json_events",
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
            ATTR_SOURCE: "geo_json_events",
        }
        assert round(abs(float(state.state) - 25.5), 7) == 0

        # Simulate an update - two existing, one new entry,
        # one outdated entry
        mock_feed_update.return_value = (
            "OK",
            [mock_entry_1, mock_entry_4, mock_entry_3],
        )
        async_fire_time_changed(hass, utcnow + timedelta(seconds=DEFAULT_SCAN_INTERVAL))
        await hass.async_block_till_done()

        assert len(hass.states.async_entity_ids("geo_location")) == 3

        # Simulate an update - empty data, but successful update,
        # so no changes to entities.
        mock_feed_update.return_value = "OK_NO_DATA", None
        async_fire_time_changed(
            hass, utcnow + 2 * timedelta(seconds=DEFAULT_SCAN_INTERVAL)
        )
        await hass.async_block_till_done()

        assert len(hass.states.async_entity_ids("geo_location")) == 3

        # Simulate an update - empty data, removes all entities
        mock_feed_update.return_value = "ERROR", None
        async_fire_time_changed(
            hass, utcnow + 3 * timedelta(seconds=DEFAULT_SCAN_INTERVAL)
        )
        await hass.async_block_till_done()

        assert len(hass.states.async_entity_ids("geo_location")) == 0


async def test_remove_orphaned_entities(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test removing orphaned geolocation entities."""
    config_entry.add_to_hass(hass)

    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "geo_location", "geo_json_events", "1", config_entry=config_entry
    )
    entity_registry.async_get_or_create(
        "geo_location", "geo_json_events", "2", config_entry=config_entry
    )
    entity_registry.async_get_or_create(
        "geo_location", "geo_json_events", "3", config_entry=config_entry
    )

    # There should now be 3 "orphaned" entries available which will be removed
    # when the component is set up.
    entries = async_entries_for_config_entry(entity_registry, config_entry.entry_id)
    assert len(entries) == 3

    # Set up a mock feed entry for this test.
    mock_entry_1 = _generate_mock_feed_entry(
        "1234",
        "Title 1",
        15.5,
        (38.0, -3.0),
    )

    with patch("aio_geojson_client.feed.GeoJsonFeed.update") as mock_feed_update:
        mock_feed_update.return_value = "OK", [mock_entry_1]
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # 1 geolocation entity.
        entries = async_entries_for_config_entry(entity_registry, config_entry.entry_id)
        assert len(entries) == 1

        assert len(hass.states.async_entity_ids("geo_location")) == 1
