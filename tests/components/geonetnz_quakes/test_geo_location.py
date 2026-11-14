"""The tests for the GeoNet NZ Quakes Feed integration."""

import datetime as dt
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import async_fire_time_changed

from homeassistant.components.geo_location import GeolocationEntityStateAttribute
from homeassistant.components.geonetnz_quakes import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.components.geonetnz_quakes.geo_location import (
    ATTR_DEPTH,
    ATTR_EXTERNAL_ID,
    ATTR_LOCALITY,
    ATTR_MAGNITUDE,
    ATTR_MMI,
    ATTR_QUALITY,
)
from homeassistant.const import (
    ATTR_TIME,
    CONF_RADIUS,
    EVENT_HOMEASSISTANT_START,
    EntityStateAttribute,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import _generate_mock_feed_entry

CONFIG = {DOMAIN: {CONF_RADIUS: 200}}


async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the general setup of the integration."""
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry(
        "1234",
        "Title 1",
        15.5,
        (38.0, -3.0),
        locality="Locality 1",
        attribution="Attribution 1",
        time=dt.datetime(2018, 9, 22, 8, 0, tzinfo=dt.UTC),
        magnitude=5.7,
        mmi=5,
        depth=10.5,
        quality="best",
    )
    mock_entry_2 = _generate_mock_feed_entry(
        "2345", "Title 2", 20.5, (38.1, -3.1), magnitude=4.6
    )
    mock_entry_3 = _generate_mock_feed_entry(
        "3456", "Title 3", 25.5, (38.2, -3.2), locality="Locality 3"
    )
    mock_entry_4 = _generate_mock_feed_entry("4567", "Title 4", 12.5, (38.3, -3.3))

    # Patching 'utcnow' to gain more control over the timed update.
    utcnow = dt_util.utcnow()
    freezer.move_to(utcnow)
    with patch("aio_geojson_client.feed.GeoJsonFeed.update") as mock_feed_update:
        mock_feed_update.return_value = "OK", [mock_entry_1, mock_entry_2, mock_entry_3]
        assert await async_setup_component(hass, DOMAIN, CONFIG)
        await hass.async_block_till_done()
        # Artificially trigger update and collect events.
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        # 3 geolocation and 1 sensor entities
        assert (
            len(hass.states.async_entity_ids("geo_location"))
            + len(hass.states.async_entity_ids("sensor"))
            == 4
        )
        assert len(entity_registry.entities) == 4

        state = hass.states.get("geo_location.title_1")
        assert state is not None
        assert state.name == "Title 1"
        assert state.attributes == {
            ATTR_EXTERNAL_ID: "1234",
            EntityStateAttribute.LATITUDE: 38.0,
            EntityStateAttribute.LONGITUDE: -3.0,
            EntityStateAttribute.FRIENDLY_NAME: "Title 1",
            ATTR_LOCALITY: "Locality 1",
            EntityStateAttribute.ATTRIBUTION: "Attribution 1",
            ATTR_TIME: dt.datetime(2018, 9, 22, 8, 0, tzinfo=dt.UTC),
            ATTR_MAGNITUDE: 5.7,
            ATTR_DEPTH: 10.5,
            ATTR_MMI: 5,
            ATTR_QUALITY: "best",
            EntityStateAttribute.UNIT_OF_MEASUREMENT: UnitOfLength.KILOMETERS,
            GeolocationEntityStateAttribute.SOURCE: "geonetnz_quakes",
            EntityStateAttribute.ICON: "mdi:pulse",
        }
        assert float(state.state) == 15.5

        state = hass.states.get("geo_location.title_2")
        assert state is not None
        assert state.name == "Title 2"
        assert state.attributes == {
            ATTR_EXTERNAL_ID: "2345",
            EntityStateAttribute.LATITUDE: 38.1,
            EntityStateAttribute.LONGITUDE: -3.1,
            EntityStateAttribute.FRIENDLY_NAME: "Title 2",
            ATTR_MAGNITUDE: 4.6,
            EntityStateAttribute.UNIT_OF_MEASUREMENT: UnitOfLength.KILOMETERS,
            GeolocationEntityStateAttribute.SOURCE: "geonetnz_quakes",
            EntityStateAttribute.ICON: "mdi:pulse",
        }
        assert float(state.state) == 20.5

        state = hass.states.get("geo_location.title_3")
        assert state is not None
        assert state.name == "Title 3"
        assert state.attributes == {
            ATTR_EXTERNAL_ID: "3456",
            EntityStateAttribute.LATITUDE: 38.2,
            EntityStateAttribute.LONGITUDE: -3.2,
            EntityStateAttribute.FRIENDLY_NAME: "Title 3",
            ATTR_LOCALITY: "Locality 3",
            EntityStateAttribute.UNIT_OF_MEASUREMENT: UnitOfLength.KILOMETERS,
            GeolocationEntityStateAttribute.SOURCE: "geonetnz_quakes",
            EntityStateAttribute.ICON: "mdi:pulse",
        }
        assert float(state.state) == 25.5

        # Simulate an update - two existing, one new entry, one outdated entry
        mock_feed_update.return_value = "OK", [mock_entry_1, mock_entry_4, mock_entry_3]
        async_fire_time_changed(hass, utcnow + DEFAULT_SCAN_INTERVAL)
        await hass.async_block_till_done()

        assert (
            len(hass.states.async_entity_ids("geo_location"))
            + len(hass.states.async_entity_ids("sensor"))
            == 4
        )
        # Simulate an update - empty data, but successful update,
        # so no changes to entities.
        mock_feed_update.return_value = "OK_NO_DATA", None
        async_fire_time_changed(hass, utcnow + 2 * DEFAULT_SCAN_INTERVAL)
        await hass.async_block_till_done()

        assert (
            len(hass.states.async_entity_ids("geo_location"))
            + len(hass.states.async_entity_ids("sensor"))
            == 4
        )
        # Simulate an update - empty data, removes all entities
        mock_feed_update.return_value = "ERROR", None
        async_fire_time_changed(hass, utcnow + 3 * DEFAULT_SCAN_INTERVAL)
        await hass.async_block_till_done()

        assert (
            len(hass.states.async_entity_ids("geo_location"))
            + len(hass.states.async_entity_ids("sensor"))
            == 1
        )
        assert len(entity_registry.entities) == 1


async def test_setup_imperial(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the setup of the integration using imperial unit system."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry("1234", "Title 1", 15.5, (38.0, -3.0))

    # Patching 'utcnow' to gain more control over the timed update.
    freezer.move_to(dt_util.utcnow())
    with (
        patch("aio_geojson_client.feed.GeoJsonFeed.update") as mock_feed_update,
        patch("aio_geojson_client.feed.GeoJsonFeed.last_timestamp", create=True),
    ):
        mock_feed_update.return_value = "OK", [mock_entry_1]
        assert await async_setup_component(hass, DOMAIN, CONFIG)
        await hass.async_block_till_done()
        # Artificially trigger update and collect events.
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        assert (
            len(hass.states.async_entity_ids("geo_location"))
            + len(hass.states.async_entity_ids("sensor"))
            == 2
        )

        # Test conversion of 200 miles to kilometers.
        manager = hass.config_entries.async_loaded_entries(DOMAIN)[0].runtime_data
        # Ensure that the filter value in km is correctly set.
        assert manager._feed_manager._feed._filter_radius == 321.8688

        state = hass.states.get("geo_location.title_1")
        assert state is not None
        assert state.name == "Title 1"
        assert state.attributes == {
            ATTR_EXTERNAL_ID: "1234",
            EntityStateAttribute.LATITUDE: 38.0,
            EntityStateAttribute.LONGITUDE: -3.0,
            EntityStateAttribute.FRIENDLY_NAME: "Title 1",
            EntityStateAttribute.UNIT_OF_MEASUREMENT: "mi",
            GeolocationEntityStateAttribute.SOURCE: "geonetnz_quakes",
            EntityStateAttribute.ICON: "mdi:pulse",
        }
        # 15.5km (as defined in mock entry) has been converted to 9.6mi.
        assert float(state.state) == 9.6
