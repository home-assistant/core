"""Tests for Google Health sensor platform."""

from collections.abc import Awaitable, Callable

import pytest

from homeassistant.core import HomeAssistant

from .conftest import ROLLUP_URL, SETTINGS_URL

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
def mock_settings(aioclient_mock: AiohttpClientMocker) -> None:
    """Mock the settings endpoint to resolve user's timezone."""
    aioclient_mock.get(
        SETTINGS_URL,
        json={"timeZone": "UTC"},
    )


async def test_sensor_steps(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test standard steps sensor flow."""

    # Mock daily rollup query returning 10500 steps
    aioclient_mock.post(
        ROLLUP_URL,
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


async def test_sensor_empty_rollup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test steps sensor when the rollup endpoint returns no data."""

    aioclient_mock.post(
        ROLLUP_URL,
        json={"rollupDataPoints": []},
    )

    assert await integration_setup()

    state = hass.states.get("sensor.google_health_steps")
    assert state is not None
    assert state.state == "0"
