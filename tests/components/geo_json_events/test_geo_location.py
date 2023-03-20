"""The tests for the geojson platform."""
from datetime import timedelta
from unittest.mock import ANY, call, patch

from aio_geojson_generic_client import GenericFeed

from homeassistant.components import geo_location
from homeassistant.const import (
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    EVENT_HOMEASSISTANT_START,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.components.geo_json_events import _generate_mock_feed_entry
from tests.components.geo_json_events.conftest import URL

CONFIG_LEGACY = {
    geo_location.DOMAIN: [
        {
            "platform": "geo_json_events",
            CONF_URL: URL,
            CONF_RADIUS: 190,
            CONF_SCAN_INTERVAL: timedelta(minutes=2),
        }
    ]
}


async def test_setup_as_legacy_platform(hass: HomeAssistant) -> None:
    """Test the setup with YAML legacy configuration."""
    # Set up some mock feed entries for this test.
    mock_entry_1 = _generate_mock_feed_entry("1234", "Title 1", 20.5, (-31.1, 150.1))

    with patch(
        "aio_geojson_generic_client.feed_manager.GenericFeed",
        wraps=GenericFeed,
    ) as mock_feed, patch(
        "aio_geojson_client.feed.GeoJsonFeed.update"
    ) as mock_feed_update:
        mock_feed_update.return_value = "OK", [mock_entry_1]

        assert await async_setup_component(hass, geo_location.DOMAIN, CONFIG_LEGACY)
        await hass.async_block_till_done()

        # Artificially trigger update.
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        await hass.async_block_till_done()

        assert len(hass.states.async_entity_ids("geo_location")) == 1

        assert mock_feed.call_args == call(ANY, ANY, URL, filter_radius=190.0)
