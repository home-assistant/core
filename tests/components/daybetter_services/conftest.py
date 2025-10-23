"""Configuration for pytest."""

from unittest.mock import patch

import pytest

from homeassistant.components.daybetter_services.const import CONF_TOKEN, DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


@pytest.fixture
def config_entry() -> ConfigEntry:
    """Create a mock config entry."""
    return ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="DayBetter Services",
        data={CONF_TOKEN: "test_token_12345"},
        source="user",
        options={},
        entry_id="test_entry_id",
        discovery_keys={},
        unique_id=None,
        subentries_data={},
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> ConfigEntry:
    """Set up the DayBetter Services integration in Home Assistant."""
    with (
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_devices",
            return_value=[],
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_pids",
            return_value={},
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_device_statuses",
            return_value=[],
        ),
        patch(
            "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.close",
            return_value=None,
        ),
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        return config_entry
