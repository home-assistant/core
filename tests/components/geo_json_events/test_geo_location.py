"""The tests for the geojson platform."""

from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time

from homeassistant.components.geo_json_events.const import (
    ATTR_EXTERNAL_ID,
    DEFAULT_UPDATE_INTERVAL,
)
from homeassistant.components.geo_location import (
    ATTR_SOURCE,
    DOMAIN as GEO_LOCATION_DOMAIN,
)
from homeassistant.const import (
    ATTR_FRIENDLY_NAME,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import _generate_mock_feed_entry
from .conftest import URL

from tests.common import MockConfigEntry, async_fire_time_changed

CONFIG_LEGACY = {
    GEO_LOCATION_DOMAIN: [
        {
            "platform": "geo_json_events",
            CONF_URL: URL,
            CONF_RADIUS: 190,
            CONF_SCAN_INTERVAL: timedelta(minutes=2),
        }
    ]
}


async def test_entity_lifecycle(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test entity lifecycle.."""
    config_entry.add_to_hass(hass)
    # Set up a mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry(
        "1234",
        "Title 1",
        15.5,
        (-31.0, 150.0),
        {ATTR_NAME: "Properties 1"},
    )
    mock_entry_2 = _generate_mock_feed_entry(
        "2345", "271310188", 20.5, (-31.1, 150.1), {ATTR_NAME: 271310188}
    )
    mock_entry_3 = _generate_mock_feed_entry("3456", "Title 3", 25.5, (-31.2, 150.2))
    mock_entry_4 = _generate_mock_feed_entry("4567", "Title 4", 12.5, (-31.3, 150.3))

    utcnow = dt_util.utcnow()
    with (
        freeze_time(utcnow),
        patch("aio_geojson_client.feed.GeoJsonFeed.update") as mock_feed_update,
    ):
        mock_feed_update.return_value = "OK", [mock_entry_1, mock_entry_2, mock_entry_3]

        # Load config entry.
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # 3 geolocation and 1 sensor entities
        assert len(hass.states.async_entity_ids(GEO_LOCATION_DOMAIN)) == 3
        assert len(entity_registry.entities) == 3

        state = hass.states.get(f"{GEO_LOCATION_DOMAIN}.properties_1")
        assert state is not None
        assert state.name == "Properties 1"
        assert state.attributes == {
            ATTR_EXTERNAL_ID: "1234",
            ATTR_LATITUDE: -31.0,
            ATTR_LONGITUDE: 150.0,
            ATTR_FRIENDLY_NAME: "Properties 1",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfLength.KILOMETERS,
            ATTR_SOURCE: "geo_json_events",
        }
        assert round(abs(float(state.state) - 15.5), 7) == 0

        state = hass.states.get(f"{GEO_LOCATION_DOMAIN}.271310188")
        assert state is not None
        assert state.name == "271310188"
        assert state.attributes == {
            ATTR_EXTERNAL_ID: "2345",
            ATTR_LATITUDE: -31.1,
            ATTR_LONGITUDE: 150.1,
            ATTR_FRIENDLY_NAME: "271310188",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfLength.KILOMETERS,
            ATTR_SOURCE: "geo_json_events",
        }
        assert round(abs(float(state.state) - 20.5), 7) == 0

        state = hass.states.get(f"{GEO_LOCATION_DOMAIN}.title_3")
        assert state is not None
        assert state.name == "Title 3"
        assert state.attributes == {
            ATTR_EXTERNAL_ID: "3456",
            ATTR_LATITUDE: -31.2,
            ATTR_LONGITUDE: 150.2,
            ATTR_FRIENDLY_NAME: "Title 3",
            ATTR_UNIT_OF_MEASUREMENT: UnitOfLength.KILOMETERS,
            ATTR_SOURCE: "geo_json_events",
        }
        assert round(abs(float(state.state) - 25.5), 7) == 0

        # Simulate an update - two existing, one new entry,
        # one outdated entry
        mock_feed_update.return_value = (
            "OK",
            [mock_entry_1, mock_entry_4, mock_entry_3],
        )
        async_fire_time_changed(hass, utcnow + DEFAULT_UPDATE_INTERVAL)
        await hass.async_block_till_done()

        assert len(hass.states.async_entity_ids(GEO_LOCATION_DOMAIN)) == 3

        # Simulate an update - empty data, but successful update,
        # so no changes to entities.
        mock_feed_update.return_value = "OK_NO_DATA", None
        async_fire_time_changed(hass, utcnow + 2 * DEFAULT_UPDATE_INTERVAL)
        await hass.async_block_till_done()

        assert len(hass.states.async_entity_ids(GEO_LOCATION_DOMAIN)) == 3

        # Simulate an update - empty data, removes all entities
        mock_feed_update.return_value = "ERROR", None
        async_fire_time_changed(hass, utcnow + 3 * DEFAULT_UPDATE_INTERVAL)
        await hass.async_block_till_done()

        assert len(hass.states.async_entity_ids(GEO_LOCATION_DOMAIN)) == 0
