"""The tests for the GDACS Feed integration."""
from homeassistant.components import gdacs
from homeassistant.components.gdacs import DEFAULT_SCAN_INTERVAL
from homeassistant.components.gdacs.sensor import (
    ATTR_CREATED,
    ATTR_LAST_UPDATE,
    ATTR_LAST_UPDATE_SUCCESSFUL,
    ATTR_REMOVED,
    ATTR_STATUS,
    ATTR_UPDATED,
)
from homeassistant.const import (
    ATTR_ICON,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_RADIUS,
    EVENT_HOMEASSISTANT_START,
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
from tests.common import async_fire_time_changed
from tests.components.gdacs import _generate_mock_feed_entry

CONFIG = {gdacs.DOMAIN: {CONF_RADIUS: 200}}


async def test_setup(hass, legacy_patchable_time):
    """Test the general setup of the integration."""
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry(
        "1234", "Title 1", 15.5, (38.0, -3.0), attribution="Attribution 1",
    )
    mock_entry_2 = _generate_mock_feed_entry("2345", "Title 2", 20.5, (38.1, -3.1),)
    mock_entry_3 = _generate_mock_feed_entry("3456", "Title 3", 25.5, (38.2, -3.2),)
    mock_entry_4 = _generate_mock_feed_entry("4567", "Title 4", 12.5, (38.3, -3.3))

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

        state = hass.states.get("sensor.gdacs_32_87336_117_22743")
        assert state is not None
        assert int(state.state) == 3
        assert state.name == "GDACS (32.87336, -117.22743)"
        attributes = state.attributes
        assert attributes[ATTR_STATUS] == "OK"
        assert attributes[ATTR_CREATED] == 3
        assert attributes[ATTR_LAST_UPDATE].tzinfo == dt_util.UTC
        assert attributes[ATTR_LAST_UPDATE_SUCCESSFUL].tzinfo == dt_util.UTC
        assert attributes[ATTR_LAST_UPDATE] == attributes[ATTR_LAST_UPDATE_SUCCESSFUL]
        assert attributes[ATTR_UNIT_OF_MEASUREMENT] == "alerts"
        assert attributes[ATTR_ICON] == "mdi:alert"

        # Simulate an update - two existing, one new entry, one outdated entry
        mock_feed_update.return_value = "OK", [mock_entry_1, mock_entry_4, mock_entry_3]
        async_fire_time_changed(hass, utcnow + DEFAULT_SCAN_INTERVAL)
        await hass.async_block_till_done()

        all_states = hass.states.async_all()
        assert len(all_states) == 4

        state = hass.states.get("sensor.gdacs_32_87336_117_22743")
        attributes = state.attributes
        assert attributes[ATTR_CREATED] == 1
        assert attributes[ATTR_UPDATED] == 2
        assert attributes[ATTR_REMOVED] == 1

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

        state = hass.states.get("sensor.gdacs_32_87336_117_22743")
        attributes = state.attributes
        assert attributes[ATTR_REMOVED] == 3
