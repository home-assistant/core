"""Tests for Google Health sensor platform."""

from collections.abc import Awaitable, Callable

from homeassistant.components.google_health.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import STEPS_ROLLUP_URL, WEIGHT_URL

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensor_steps(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test standard steps sensor flow."""

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
    aioclient_mock.get(
        WEIGHT_URL,
        json={"dataPoints": []},
    )

    # Setup the integration
    assert await integration_setup()

    state = hass.states.get("sensor.google_health_steps")
    assert state is not None
    assert state.state == "10500"
    assert state.attributes.get("unit_of_measurement") == "steps"
    assert state.attributes.get("icon") == "mdi:walk"

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, config_entry.entry_id)})
    assert device is not None
    assert device.name == config_entry.title


async def test_sensor_weight(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test weight sensor flow."""

    aioclient_mock.post(
        STEPS_ROLLUP_URL,
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

    # Setup the integration
    assert await integration_setup()

    state = hass.states.get("sensor.google_health_weight")
    assert state is not None
    assert state.state == "80.0"
    assert state.attributes.get("unit_of_measurement") == "kg"
    assert state.attributes.get("device_class") == "weight"


async def test_sensor_empty_rollup(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
    integration_setup: Callable[[], Awaitable[bool]],
) -> None:
    """Test steps sensor when the rollup endpoint returns no data."""

    aioclient_mock.post(
        STEPS_ROLLUP_URL,
        json={"rollupDataPoints": []},
    )
    aioclient_mock.get(
        WEIGHT_URL,
        json={"dataPoints": []},
    )

    assert await integration_setup()

    state = hass.states.get("sensor.google_health_steps")
    assert state is not None
    assert state.state == "0"
