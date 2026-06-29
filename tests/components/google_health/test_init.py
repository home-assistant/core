"""Tests for Google Health integration lifecycle (init/unloading)."""

from collections.abc import Awaitable, Callable

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from .conftest import STEPS_ROLLUP_URL, WEIGHT_URL

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

    # Setup the integration
    assert await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.LOADED

    # Verify both entities exist
    assert hass.states.get("sensor.google_health_steps") is not None
    assert hass.states.get("sensor.google_health_weight") is not None

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
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_setup_missing_scopes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test setup fails and triggers reauth if token has missing profile scope."""
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
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


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

    # Steps sensor entity should not exist
    state = hass.states.get("sensor.google_health_steps")
    assert state is None

    # Weight sensor entity should exist
    assert hass.states.get("sensor.google_health_weight") is not None


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

    # Weight sensor entity should not exist
    state = hass.states.get("sensor.google_health_weight")
    assert state is None

    # Steps sensor entity should exist
    assert hass.states.get("sensor.google_health_steps") is not None
