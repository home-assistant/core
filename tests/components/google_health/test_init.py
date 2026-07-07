"""Tests for Google Health integration lifecycle (init/unloading)."""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, patch

from google_health_api.exceptions import (
    GoogleHealthApiError,
    HealthApiForbiddenException,
)
import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_google_health_client")
async def test_setup_and_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test standard setup and unloading of the config entry."""
    assert await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.LOADED

    assert hass.states.get("sensor.google_health_steps") is not None
    assert hass.states.get("sensor.google_health_distance") is not None
    assert hass.states.get("sensor.google_health_weight") is not None
    assert hass.states.get("sensor.google_health_resting_heart_rate") is not None

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is config_entries.ConfigEntryState.NOT_LOADED


async def test_setup_api_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_google_health_client: AsyncMock,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test setup error retry handling when API fails."""
    mock_google_health_client.steps.today.side_effect = GoogleHealthApiError

    assert not await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.SETUP_RETRY


async def test_setup_auth_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_google_health_client: AsyncMock,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test setup error when API returns auth or forbidden errors."""
    mock_google_health_client.steps.today.side_effect = HealthApiForbiddenException

    assert not await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0


@pytest.mark.usefixtures("mock_google_health_client")
@pytest.mark.parametrize(
    "scopes", ["https://www.googleapis.com/auth/health.activity_and_fitness.readonly"]
)
async def test_setup_missing_scopes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test setup fails if token has missing profile scope."""
    assert not await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0


@pytest.mark.usefixtures("mock_google_health_client")
@pytest.mark.parametrize(
    "scopes",
    [
        [
            "https://www.googleapis.com/auth/googlehealth.profile.readonly",
            "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
        ]
    ],
)
async def test_setup_missing_activity_scope(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test setup succeeds but steps sensor is not added if activity scope is missing."""
    assert await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.LOADED

    assert hass.states.get("sensor.google_health_steps") is None
    assert hass.states.get("sensor.google_health_distance") is None

    assert hass.states.get("sensor.google_health_weight") is not None
    assert hass.states.get("sensor.google_health_resting_heart_rate") is not None


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
async def test_setup_missing_measurements_scope(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test setup succeeds but weight sensor is not added if measurements scope is missing."""
    assert await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.LOADED

    assert hass.states.get("sensor.google_health_weight") is None
    assert hass.states.get("sensor.google_health_resting_heart_rate") is None

    assert hass.states.get("sensor.google_health_steps") is not None
    assert hass.states.get("sensor.google_health_distance") is not None


async def test_setup_oauth_implementation_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.google_health.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is config_entries.ConfigEntryState.SETUP_RETRY
