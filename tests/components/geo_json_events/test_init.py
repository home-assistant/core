"""Define tests for the GeoJSON Events general setup."""
from unittest.mock import ANY, patch

from homeassistant.components.geo_json_events.const import DOMAIN, FEED
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import async_entries_for_config_entry
from homeassistant.util.unit_system import IMPERIAL_SYSTEM

from tests.components.geo_json_events import _generate_mock_feed_entry


async def test_component_unload_config_entry(hass, config_entry):
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


async def test_remove_orphaned_entities(hass, config_entry):
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

        # 1 geolocation and 1 sensor entity.
        entries = async_entries_for_config_entry(entity_registry, config_entry.entry_id)
        assert len(entries) == 2

        assert (
            len(hass.states.async_entity_ids("geo_location"))
            + len(hass.states.async_entity_ids("sensor"))
            == 2
        )


async def test_radius_imperial(hass, config_entry):
    """Test conversion of radius from imperial to metric."""
    hass.config.units = IMPERIAL_SYSTEM

    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.geo_json_events.GeoJsonEventsFeedEntityCoordinator"
    ) as mock_coordinator:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        mock_coordinator.assert_called_once_with(ANY, ANY, 40.2336)
