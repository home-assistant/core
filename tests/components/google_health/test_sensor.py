"""Tests for Google Health sensor platform."""

from collections.abc import Awaitable, Callable

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensor_steps(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test standard steps sensor flow."""
    # Mock settings to resolve user's timezone
    aioclient_mock.get(
        "https://health.googleapis.com/v4/users/me/settings",
        json={"timeZone": "UTC"},
    )

    # Mock daily rollup query returning 10500 steps
    aioclient_mock.post(
        "https://health.googleapis.com/v4/users/me/dataTypes/steps/dataPoints:dailyRollUp",
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

    # Setup the integration
    assert await integration_setup()

    state = hass.states.get("sensor.google_health_steps")
    assert state is not None
    assert state.state == "10500"
    assert state.attributes.get("unit_of_measurement") == "steps"
    assert state.attributes.get("icon") == "mdi:walk"

    # Unload integration
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_sensor_empty_rollup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test steps sensor when the rollup endpoint returns no data."""
    aioclient_mock.get(
        "https://health.googleapis.com/v4/users/me/settings",
        json={"timeZone": "UTC"},
    )

    aioclient_mock.post(
        "https://health.googleapis.com/v4/users/me/dataTypes/steps/dataPoints:dailyRollUp",
        json={"rollupDataPoints": []},
    )

    assert await integration_setup()

    state = hass.states.get("sensor.google_health_steps")
    assert state is not None
    assert state.state == "0"


async def test_sensor_api_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test steps sensor error handling when API fails."""
    aioclient_mock.get(
        "https://health.googleapis.com/v4/users/me/settings",
        json={"timeZone": "UTC"},
    )

    aioclient_mock.post(
        "https://health.googleapis.com/v4/users/me/dataTypes/steps/dataPoints:dailyRollUp",
        status=500,
    )

    assert not await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.SETUP_RETRY


async def test_sensor_auth_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test steps sensor error handling when API fails with auth/forbidden error."""
    aioclient_mock.get(
        "https://health.googleapis.com/v4/users/me/settings",
        json={"timeZone": "UTC"},
    )

    aioclient_mock.post(
        "https://health.googleapis.com/v4/users/me/dataTypes/steps/dataPoints:dailyRollUp",
        status=403,
    )

    assert not await integration_setup()
    assert config_entry.state is config_entries.ConfigEntryState.SETUP_ERROR
