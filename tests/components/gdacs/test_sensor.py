"""The tests for the GDACS Feed integration."""

from unittest.mock import patch

from freezegun import freeze_time

from homeassistant.components import gdacs
from homeassistant.components.gdacs import DEFAULT_SCAN_INTERVAL
from homeassistant.components.gdacs.const import CONF_CATEGORIES
from homeassistant.components.gdacs.sensor import (
    ATTR_CREATED,
    ATTR_LAST_UPDATE,
    ATTR_LAST_UPDATE_SUCCESSFUL,
    ATTR_REMOVED,
    ATTR_STATUS,
    ATTR_UPDATED,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_START,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import _generate_mock_feed_entry

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_setup(hass: HomeAssistant) -> None:
    """Test the general setup of the integration."""
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry(
        "1234",
        "Title 1",
        15.5,
        (38.0, -3.0),
        attribution="Attribution 1",
    )
    mock_entry_2 = _generate_mock_feed_entry(
        "2345",
        "Title 2",
        20.5,
        (38.1, -3.1),
    )
    mock_entry_3 = _generate_mock_feed_entry(
        "3456",
        "Title 3",
        25.5,
        (38.2, -3.2),
    )
    mock_entry_4 = _generate_mock_feed_entry("4567", "Title 4", 12.5, (38.3, -3.3))

    # Patching 'utcnow' to gain more control over the timed update.
    utcnow = dt_util.utcnow()
    with (
        freeze_time(utcnow),
        patch("aio_georss_client.feed.GeoRssFeed.update") as mock_feed_update,
    ):
        mock_feed_update.return_value = "OK", [mock_entry_1, mock_entry_2, mock_entry_3]
        latitude = 32.87336
        longitude = -117.22743
        radius = 200
        entry_data = {
            CONF_RADIUS: radius,
            CONF_LATITUDE: latitude,
            CONF_LONGITUDE: longitude,
            CONF_CATEGORIES: [],
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL.seconds,
        }
        config_entry = MockConfigEntry(
            domain=gdacs.DOMAIN,
            title=f"{latitude}, {longitude}",
            data=entry_data,
            unique_id="my_very_unique_id",
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        # Artificially trigger update and collect events.
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        # 3 geolocation and 1 sensor entities
        assert (
            len(hass.states.async_entity_ids("geo_location"))
            + len(hass.states.async_entity_ids("sensor"))
            == 4
        )

        state = hass.states.get("sensor.32_87336_117_22743")
        assert state is not None
        assert int(state.state) == 3
        assert state.name == "32.87336, -117.22743"
        attributes = state.attributes
        assert attributes[ATTR_STATUS] == "OK"
        assert attributes[ATTR_CREATED] == 3
        assert attributes[ATTR_LAST_UPDATE].tzinfo == dt_util.UTC
        assert attributes[ATTR_LAST_UPDATE_SUCCESSFUL].tzinfo == dt_util.UTC
        assert attributes[ATTR_LAST_UPDATE] == attributes[ATTR_LAST_UPDATE_SUCCESSFUL]
        assert attributes[ATTR_UNIT_OF_MEASUREMENT] == "alerts"

        # Simulate an update - two existing, one new entry, one outdated entry
        mock_feed_update.return_value = "OK", [mock_entry_1, mock_entry_4, mock_entry_3]
        async_fire_time_changed(hass, utcnow + DEFAULT_SCAN_INTERVAL)
        await hass.async_block_till_done()

        assert (
            len(hass.states.async_entity_ids("geo_location"))
            + len(hass.states.async_entity_ids("sensor"))
            == 4
        )

        state = hass.states.get("sensor.32_87336_117_22743")
        attributes = state.attributes
        assert attributes[ATTR_CREATED] == 1
        assert attributes[ATTR_UPDATED] == 2
        assert attributes[ATTR_REMOVED] == 1

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

        state = hass.states.get("sensor.32_87336_117_22743")
        attributes = state.attributes
        assert attributes[ATTR_REMOVED] == 3
