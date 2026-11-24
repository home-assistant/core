"""Define tests for the GDACS general setup."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.gdacs.const import CONF_CATEGORIES, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_SYSTEM,
)
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)


async def test_component_unload_config_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test that loading and unloading of a config entry works."""
    config_entry.add_to_hass(hass)
    with patch("aio_georss_gdacs.GdacsFeedManager.update") as mock_feed_manager_update:
        # Load config entry.
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_feed_manager_update.call_count == 1

        # Unload config entry.
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("units", "radius"),
    [
        pytest.param(US_CUSTOMARY_SYSTEM, 40233.6, id="unhinged"),
        pytest.param(METRIC_SYSTEM, 25000, id="normal"),
    ],
)
async def test_migrate_entry(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    units: UnitSystem,
    radius: float,
) -> None:
    """Test migration of config entry."""
    hass.config.units = units

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_LATITUDE: -41.2,
            CONF_LONGITUDE: 174.7,
            CONF_RADIUS: 25,
            CONF_UNIT_SYSTEM: "metric",
            CONF_SCAN_INTERVAL: 300.0,
            "categories": ["DR", "WF"],
        },
        title="-41.2, 174.7",
        unique_id="-41.2, 174.7",
    )
    config_entry.add_to_hass(hass)
    with patch("aio_georss_gdacs.GdacsFeedManager.update"):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert config_entry.data == {
        CONF_CATEGORIES: ["DR", "WF"],
        CONF_LOCATION: {
            CONF_LATITUDE: -41.2,
            CONF_LONGITUDE: 174.7,
            CONF_RADIUS: radius,
        },
    }
