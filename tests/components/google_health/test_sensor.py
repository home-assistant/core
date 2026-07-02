"""Tests for Google Health sensor platform."""

from collections.abc import Awaitable, Callable

from homeassistant.components.google_health.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import (
    DISTANCE_ROLLUP_URL,
    RESTING_HEART_RATE_URL,
    STEPS_ROLLUP_URL,
    WEIGHT_URL,
)

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensor_steps_and_distance(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test standard steps and distance sensor flow."""

    # Mock daily rollup query returning 10500 steps
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
        json={"dataPoints": []},
    )
    aioclient_mock.get(
        RESTING_HEART_RATE_URL,
        json={"dataPoints": []},
    )

    # Setup the integration
    assert await integration_setup()

    state = hass.states.get("sensor.google_health_steps")
    assert state is not None
    assert state.state == "10500"
    assert state.attributes.get("unit_of_measurement") == "steps"
    assert state.attributes.get("icon") == "mdi:walk"

    distance_state = hass.states.get("sensor.google_health_distance")
    assert distance_state is not None
    assert distance_state.state == "5000.0"
    assert distance_state.attributes.get("unit_of_measurement") == "m"
    assert distance_state.attributes.get("device_class") == "distance"

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, config_entry.entry_id)})
    assert device is not None
    assert device.name == config_entry.title


async def test_sensor_weight_and_resting_heart_rate(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test weight and resting heart rate sensor flow."""

    aioclient_mock.post(
        STEPS_ROLLUP_URL,
        json={"rollupDataPoints": []},
    )
    aioclient_mock.post(
        DISTANCE_ROLLUP_URL,
        json={"rollupDataPoints": []},
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

    state = hass.states.get("sensor.google_health_weight")
    assert state is not None
    assert state.state == "80.0"
    assert state.attributes.get("unit_of_measurement") == "kg"
    assert state.attributes.get("device_class") == "weight"

    hr_state = hass.states.get("sensor.google_health_resting_heart_rate")
    assert hr_state is not None
    assert hr_state.state == "65"
    assert hr_state.attributes.get("unit_of_measurement") == "bpm"
    assert hr_state.attributes.get("icon") == "mdi:heart-pulse"


async def test_sensor_empty_rollup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test steps and distance sensors when the rollup endpoint returns no data."""

    aioclient_mock.post(
        STEPS_ROLLUP_URL,
        json={"rollupDataPoints": []},
    )
    aioclient_mock.post(
        DISTANCE_ROLLUP_URL,
        json={"rollupDataPoints": []},
    )
    aioclient_mock.get(
        WEIGHT_URL,
        json={"dataPoints": []},
    )
    aioclient_mock.get(
        RESTING_HEART_RATE_URL,
        json={"dataPoints": []},
    )

    assert await integration_setup()

    steps_state = hass.states.get("sensor.google_health_steps")
    assert steps_state is not None
    assert steps_state.state == "0"

    distance_state = hass.states.get("sensor.google_health_distance")
    assert distance_state is not None
    assert distance_state.state == "0.0"
