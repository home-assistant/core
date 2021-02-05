"""Tests for FMI."""

from unittest.mock import patch

from homeassistant.components.fmi.const import DOMAIN

from .const import MOCK_CURRENT, MOCK_FORECAST

from tests.common import MockConfigEntry


async def init_integration(hass, offset=12, unsupported_icon=False) -> MockConfigEntry:
    """Set up the FMI integration in Home Assistant."""
    options = {}
    if offset:
        options["offset"] = 12

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="0123456",
        data={
            "offset": 12,
            "latitude": 55.55,
            "longitude": 122.12,
            "name": "Home",
        },
        options=options,
    )

    current = MOCK_CURRENT
    forecast = MOCK_FORECAST

    with patch(
        "homeassistant.components.fmi.weather_by_coordinates",
        return_value=current,
    ), patch(
        "homeassistant.components.fmi.forecast_by_coordinates",
        return_value=forecast,
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
