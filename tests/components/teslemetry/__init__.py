"""Tests for the Teslemetry integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.teslemetry.const import DOMAIN, TeslemetryState
from homeassistant.core import HomeAssistant

from .const import CONFIG

from tests.common import MockConfigEntry, load_json_object_fixture


async def setup_platform(hass: HomeAssistant, side_effect=None):
    """Set up the Tessie platform."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
    )
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.teslemetry.Teslemetry",
    ) as teslemetry_mock:
        teslemetry_mock.return_value.products = AsyncMock(
            load_json_object_fixture("products.json", DOMAIN)
        )
        teslemetry_mock.return_value.products.side_effect = side_effect

        teslemetry_mock.return_value.vehicle.specific.return_value.wake_up = AsyncMock(
            {"response": {"state": TeslemetryState.ONLINE}, "error": None}
        )
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    return mock_entry
