"""Define tests for the GeoNet NZ Quakes general setup."""

from unittest.mock import patch

from homeassistant.components.geonetnz_quakes.const import (
    CONF_MINIMUM_MAGNITUDE,
    CONF_MMI,
    DOMAIN,
)
from homeassistant.config_entries import async_setup_component
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_RADIUS
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.helpers import issue_registry as ir


async def test_component_unload_config_entry(hass: HomeAssistant, config_entry) -> None:
    """Test that loading and unloading of a config entry works."""
    config_entry.add_to_hass(hass)
    with patch(
        "aio_geojson_geonetnz_quakes.GeonetnzQuakesFeedManager.update"
    ) as mock_feed_manager_update:
        # Load config entry.
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_feed_manager_update.call_count == 1

        # Unload config entry.
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()


async def test_import(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test yaml import."""
    with patch("aio_geojson_geonetnz_quakes.GeonetnzQuakesFeedManager.update"):
        await async_setup_component(
            hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_LATITUDE: -41.2,
                    CONF_LONGITUDE: 174.7,
                    CONF_RADIUS: 25,
                    CONF_MMI: 2,
                    CONF_MINIMUM_MAGNITUDE: 2.5,
                },
            },
        )

    await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        domain=HOMEASSISTANT_DOMAIN,
        issue_id=f"deprecated_yaml_{DOMAIN}",
    )
