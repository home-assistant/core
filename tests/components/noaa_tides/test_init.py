"""Tests for the NOAA Tides setup."""

from unittest.mock import patch

from noaa_coops.station import Station

from homeassistant.components.noaa_tides.const import CONF_STATION_ID, DOMAIN
from homeassistant.core import HomeAssistant

from .test_config_flow import INVALID_STATION_ID

from tests.common import MockConfigEntry


async def test_no_station_id(hass: HomeAssistant) -> None:
    """Test no Station ID."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STATION_ID: None},
        unique_id=f"{'None'.lower()}",
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id) is False


async def test_invalid_station_id(hass: HomeAssistant) -> None:
    """Test invalid Station ID."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STATION_ID: INVALID_STATION_ID},
        unique_id=f"{'Unknown Name'.lower()}",
    )
    config_entry.add_to_hass(hass)

    def mock_get_metadata(self: Station):
        raise KeyError

    with patch.object(Station, "get_metadata", mock_get_metadata):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test invalid Station ID."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_STATION_ID: INVALID_STATION_ID},
        unique_id=f"{'Unknown Name'.lower()}",
    )
    config_entry.add_to_hass(hass)

    def mock_get_metadata(self: Station):
        raise ConnectionError

    with patch.object(Station, "get_metadata", mock_get_metadata):
        assert await hass.config_entries.async_setup(config_entry.entry_id) is False
