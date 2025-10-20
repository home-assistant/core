"""Configuration for pytest."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from homeassistant.components.daybetter_services import const


@pytest.fixture
async def init_integration(hass: HomeAssistant) -> ConfigEntry:
    """Set up the DayBetter Services integration in Home Assistant."""
    with patch(
        "homeassistant.components.daybetter_services.daybetter_api.DayBetterApi.fetch_devices",
        return_value=[],
    ):
        entry = ConfigEntry(
            version=1,
            domain=const.DOMAIN,
            title="DayBetter Services",
            data={const.CONF_TOKEN: "test_token"},
            source="user",
            options={},
            entry_id="test_entry_id",
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        return entry