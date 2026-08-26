"""Test the Monarch Money coordinator."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_cashflow_year_follows_configured_time_zone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
) -> None:
    """Test the cashflow window uses the year of the configured time zone.

    The clock is stopped at a moment that is still 2025 in UTC but already 2026
    in Pacific/Kiritimati, so a query built from the host clock would ask for
    the wrong year.
    """
    await hass.config.async_set_time_zone("Pacific/Kiritimati")  # UTC+14
    freezer.move_to("2025-12-31T12:00:00+00:00")

    await setup_integration(hass, mock_config_entry)

    mock_config_api.return_value.get_cashflow_summary.assert_called_with(
        start_date="2026-01-01", end_date="2026-12-31"
    )
