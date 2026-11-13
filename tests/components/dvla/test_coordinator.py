"""Tests for the DVLA data update coordinator."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

from aio_dvla_vehicle_enquiry import (
    DVLAAuthError,
    DVLAError,
    DVLAInvalidRegistrationError,
    DVLARateLimitError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant


@pytest.mark.parametrize(
    ("error", "retry_delay"),
    [
        pytest.param(
            DVLAError("Connection failed"), timedelta(hours=1), id="connection"
        ),
        pytest.param(
            DVLARateLimitError("Too many requests"), timedelta(hours=1), id="rate_limit"
        ),
        pytest.param(DVLAAuthError("Invalid key"), timedelta(weeks=1), id="auth"),
        pytest.param(
            DVLAInvalidRegistrationError("Vehicle not found"),
            timedelta(weeks=1),
            id="registration",
        ),
    ],
)
async def test_refresh_failure_and_recovery(
    hass: HomeAssistant,
    setup_dvla_entry: Callable[[dict[str, Any] | None], Awaitable[MockConfigEntry]],
    mock_dvla_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    error: DVLAError,
    retry_delay: timedelta,
) -> None:
    """Test scheduled refresh failures retry at the appropriate cadence."""
    entry = await setup_dvla_entry()
    entity_id = "sensor.ab12cde_tax_status"

    mock_dvla_client.side_effect = error
    freezer.tick(timedelta(weeks=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert entry.state is ConfigEntryState.LOADED
    assert not hass.config_entries.flow.async_progress()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    assert mock_dvla_client.await_count == 2

    mock_dvla_client.side_effect = None
    freezer.tick(retry_delay - timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_dvla_client.await_count == 2

    freezer.tick(timedelta(minutes=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(entity_id).state == "taxed"
    assert mock_dvla_client.await_count == 3
