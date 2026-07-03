"""Tests for Google Health integration lifecycle (init/unloading)."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from .conftest import (
    DISTANCE_ROLLUP_URL,
    RESTING_HEART_RATE_URL,
    STEPS_ROLLUP_URL,
    WEIGHT_URL,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_and_unload(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test standard setup and unloading of the config entry."""
    aioclient_mock.post(
        STEPS_ROLLUP_URL,
        json={
            "rollupDataPoints": [
                {
                    "steps": {
                        "countSum": 10500,
                    },
                    "civilStartTime": {"date": {"year": 2026, "month": 6, "day": 28}},
                    "civilEndTime": {"date": {"year": 2026, "month": 6, "day": 29}},
                }
            ]
        },
    )
    aioclient_mock.post(
        DISTANCE_ROLLUP_URL,
        json={
            "rollupDataPoints": [
                {
                    "distance": {
                        "millimetersSum": 5000000,
                    },
                    "civilStartTime": {"date": {"year": 2026, "month": 6, "day": 28}},
                    "civilEndTime": {"date": {"year": 2026, "month": 6, "day": 29}},
                }
            ]
        },
    )
    aioclient_mock.get(
        WEIGHT_URL,
        json={
            "dataPoints": [
                {
                    "weight": {
                        "weightGrams": 80000.0,
                        "sampleTime": {
                            "physicalTime": "2026-06-29T00:00:00Z",
                        },
                    }
                }
            ]
        },
    )
    aioclient_mock.get(
        RESTING_HEART_RATE_URL,
        json={
            "dataPoints": [
                {
                    "dailyRestingHeartRate": {
                        "beatsPerMinute": 65,
                        "date": {"year": 2026, "month": 6, "day": 29},
                    }
                }
            ]
        },
    )

    # Setup the integration
    assert await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.LOADED

    # Verify entities exist
    assert hass.states.get("sensor.google_health_steps") is not None
    assert hass.states.get("sensor.google_health_distance") is not None
    assert hass.states.get("sensor.google_health_weight") is not None
    assert hass.states.get("sensor.google_health_resting_heart_rate") is not None

    # Unload integration
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is config_entries.ConfigEntryState.NOT_LOADED


async def test_setup_api_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test setup error retry handling when API fails."""
    aioclient_mock.post(
        STEPS_ROLLUP_URL,
        status=500,
    )

    assert not await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.SETUP_RETRY


async def test_setup_auth_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test setup error when API returns auth or forbidden errors."""
    aioclient_mock.post(
        STEPS_ROLLUP_URL,
        status=403,
    )

    assert not await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0


async def test_setup_missing_scopes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test setup fails if token has missing profile scope."""
    # Modify token to exclude profile scope
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            **config_entry.data,
            "token": {
                **config_entry.data["token"],
                "scope": "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
            },
        },
    )

    assert not await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 0


async def test_setup_missing_activity_scope(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test setup succeeds but steps sensor is not added if activity scope is missing."""
    aioclient_mock.get(
        WEIGHT_URL,
        json={
            "dataPoints": [
                {
                    "weight": {
                        "weightGrams": 80000.0,
                        "sampleTime": {
                            "physicalTime": "2026-06-29T00:00:00Z",
                        },
                    }
                }
            ]
        },
    )

    aioclient_mock.get(
        RESTING_HEART_RATE_URL,
        json={"dataPoints": []},
    )

    # Modify token to exclude activity scope
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            **config_entry.data,
            "token": {
                **config_entry.data["token"],
                "scope": (
                    "https://www.googleapis.com/auth/googlehealth.profile.readonly "
                    "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly"
                ),
            },
        },
    )

    # Setup should succeed
    assert await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.LOADED

    # Activity sensor entities should not exist
    assert hass.states.get("sensor.google_health_steps") is None
    assert hass.states.get("sensor.google_health_distance") is None

    # Body sensor entities should exist
    assert hass.states.get("sensor.google_health_weight") is not None
    assert hass.states.get("sensor.google_health_resting_heart_rate") is not None


async def test_setup_missing_measurements_scope(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test setup succeeds but weight sensor is not added if measurements scope is missing."""
    aioclient_mock.post(
        STEPS_ROLLUP_URL,
        json={
            "rollupDataPoints": [
                {
                    "steps": {
                        "countSum": 10500,
                    },
                    "civilStartTime": {"date": {"year": 2026, "month": 6, "day": 28}},
                    "civilEndTime": {"date": {"year": 2026, "month": 6, "day": 29}},
                }
            ]
        },
    )

    aioclient_mock.post(
        DISTANCE_ROLLUP_URL,
        json={"rollupDataPoints": []},
    )

    # Modify token to exclude measurements scope
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            **config_entry.data,
            "token": {
                **config_entry.data["token"],
                "scope": (
                    "https://www.googleapis.com/auth/googlehealth.profile.readonly "
                    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly"
                ),
            },
        },
    )

    # Setup should succeed
    assert await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.LOADED

    # Body sensor entities should not exist
    assert hass.states.get("sensor.google_health_weight") is None
    assert hass.states.get("sensor.google_health_resting_heart_rate") is None

    # Activity sensor entities should exist
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
