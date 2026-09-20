"""Test the Monarch Money coordinator."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    (
        "time_zone",
        "frozen_time",
        "cashflow_start_date",
        "cashflow_end_date",
        "budget_start_date",
        "budget_end_date",
    ),
    [
        pytest.param(
            "Pacific/Kiritimati",
            "2025-12-31T12:00:00+00:00",
            "2026-01-01",
            "2026-12-31",
            "2026-01-01",
            "2026-01-31",
            id="new_year_in_configured_time_zone",
        ),
        pytest.param(
            "America/Los_Angeles",
            "2024-02-29T23:30:00-08:00",
            "2024-01-01",
            "2024-12-31",
            "2024-02-01",
            "2024-02-29",
            id="leap_year",
        ),
    ],
)
async def test_query_windows_follow_configured_time_zone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
    time_zone: str,
    frozen_time: str,
    cashflow_start_date: str,
    cashflow_end_date: str,
    budget_start_date: str,
    budget_end_date: str,
) -> None:
    """Test query windows use the configured time zone.

    The clock is stopped at a moment that is still 2025 in UTC but already 2026
    in Pacific/Kiritimati, so a query built from the host clock would ask for
    the wrong year.
    """
    await hass.config.async_set_time_zone(time_zone)
    freezer.move_to(frozen_time)

    await setup_integration(hass, mock_config_entry)

    mock_config_api.return_value.get_cashflow_summary.assert_called_with(
        start_date=cashflow_start_date, end_date=cashflow_end_date
    )
    mock_config_api.return_value.get_budgets.assert_called_with(
        start_date=budget_start_date, end_date=budget_end_date
    )
