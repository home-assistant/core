"""Tests for the diagnostics data provided by the Google Health integration."""

from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest.mock import AsyncMock

from google_health_api.exceptions import GoogleHealthApiError
from google_health_api.model import ListDataPointResult, _ListDataPointsModel
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.google_health.coordinator import POLLING_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

pytestmark = pytest.mark.freeze_time("2026-07-22 00:00:00+00:00")


@pytest.mark.usefixtures("mock_google_health_client")
async def test_diagnostics_full_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics output when all coordinators have data."""
    assert await integration_setup()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics == snapshot


async def test_diagnostics_empty_data(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_google_health_client: AsyncMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics output when coordinators have no data."""
    # Mock all coordinator endpoints to return None or empty data
    mock_google_health_client.steps.today.return_value = None
    mock_google_health_client.distance.today.return_value = None
    mock_google_health_client.active_energy_burned.today.return_value = None
    mock_google_health_client.total_calories.today.return_value = None
    mock_google_health_client.floors.today.return_value = None

    mock_google_health_client.weight.list.return_value = ListDataPointResult(
        _ListDataPointsModel(data_points=[])
    )
    mock_google_health_client.daily_resting_heart_rate.list.return_value = (
        ListDataPointResult(_ListDataPointsModel(data_points=[]))
    )
    mock_google_health_client.body_fat.list.return_value = ListDataPointResult(
        _ListDataPointsModel(data_points=[])
    )

    mock_google_health_client.sleep.list.return_value = ListDataPointResult(
        _ListDataPointsModel(data_points=[])
    )

    assert await integration_setup()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics == snapshot


async def test_diagnostics_update_failed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_google_health_client: AsyncMock,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics output when coordinator update fails."""
    assert await integration_setup()

    # Trigger update failure on next refresh for activity coordinator
    mock_google_health_client.steps.today.side_effect = GoogleHealthApiError(
        "API Error"
    )

    async_fire_time_changed(
        hass,
        dt_util.utcnow() + POLLING_INTERVAL + timedelta(seconds=1),
    )
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics == snapshot


@pytest.mark.usefixtures("mock_google_health_client")
@pytest.mark.parametrize(
    "scopes",
    [
        [
            "https://www.googleapis.com/auth/googlehealth.profile.readonly",
            "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
        ]
    ],
)
async def test_diagnostics_partial_scopes(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics when only a subset of scopes is authorized."""
    assert await integration_setup()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    assert diagnostics == snapshot
