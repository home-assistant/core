"""The test for the Trend sensor platform."""
from datetime import timedelta
import logging
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant import config as hass_config, setup
from homeassistant.components.trend.const import DOMAIN
from homeassistant.const import SERVICE_RELOAD, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, get_fixture_path, mock_restore_cache


async def _setup_component(hass: HomeAssistant, params: dict[str, Any]) -> None:
    """Set up the trend component."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "trend",
                "sensors": {
                    "test_trend_sensor": params,
                },
            }
        },
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("states", "inverted", "expected_state"),
    [
        (["1", "2"], False, STATE_ON),
        (["2", "1"], False, STATE_OFF),
        (["1", "2"], True, STATE_OFF),
        (["2", "1"], True, STATE_ON),
    ],
    ids=["up", "down", "up inverted", "down inverted"],
)
async def test_basic_trend(
    hass: HomeAssistant,
    states: list[str],
    inverted: bool,
    expected_state: str,
):
    """Test trend with a basic setup."""
    await _setup_component(
        hass,
        {
            "entity_id": "sensor.test_state",
            "invert": inverted,
        },
    )

    for state in states:
        hass.states.async_set("sensor.test_state", state)
        await hass.async_block_till_done()

    assert (sensor_state := hass.states.get("binary_sensor.test_trend_sensor"))
    assert sensor_state.state == expected_state


@pytest.mark.parametrize(
    ("state_series", "inverted", "expected_states"),
    [
        (
            [[10, 0, 20, 30], [100], [0, 30, 1, 0]],
            False,
            [STATE_UNKNOWN, STATE_ON, STATE_OFF],
        ),
        (
            [[10, 0, 20, 30], [100], [0, 30, 1, 0]],
            True,
            [STATE_UNKNOWN, STATE_OFF, STATE_ON],
        ),
        (
            [[30, 20, 30, 10], [5], [30, 0, 45, 60]],
            True,
            [STATE_UNKNOWN, STATE_ON, STATE_OFF],
        ),
    ],
    ids=["up", "up inverted", "down"],
)
async def test_using_trendline(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    state_series: list[list[str]],
    inverted: bool,
    expected_states: list[str],
):
    """Test uptrend using multiple samples and trendline calculation."""
    await _setup_component(
        hass,
        {
            "entity_id": "sensor.test_state",
            "sample_duration": 10000,
            "min_gradient": 1,
            "max_samples": 25,
            "min_samples": 5,
            "invert": inverted,
        },
    )

    for idx, states in enumerate(state_series):
        for state in states:
            freezer.tick(timedelta(seconds=2))
            hass.states.async_set("sensor.test_state", state)
            await hass.async_block_till_done()

        assert (sensor_state := hass.states.get("binary_sensor.test_trend_sensor"))
        assert sensor_state.state == expected_states[idx]


@pytest.mark.parametrize(
    ("attr_values", "expected_state"),
    [
        (["1", "2"], STATE_ON),
        (["2", "1"], STATE_OFF),
    ],
    ids=["up", "down"],
)
async def test_attribute_trend(
    hass: HomeAssistant,
    attr_values: list[str],
    expected_state: str,
):
    """Test attribute uptrend."""
    await _setup_component(
        hass,
        {
            "entity_id": "sensor.test_state",
            "attribute": "attr",
        },
    )

    for attr in attr_values:
        hass.states.async_set("sensor.test_state", "State", {"attr": attr})
        await hass.async_block_till_done()

    assert (sensor_state := hass.states.get("binary_sensor.test_trend_sensor"))
    assert sensor_state.state == expected_state


async def test_max_samples(hass: HomeAssistant):
    """Test that sample count is limited correctly."""
    await _setup_component(
        hass,
        {
            "entity_id": "sensor.test_state",
            "max_samples": 3,
            "min_gradient": -1,
        },
    )

    for val in [0, 1, 2, 3, 2, 1]:
        hass.states.async_set("sensor.test_state", val)
        await hass.async_block_till_done()

    assert (state := hass.states.get("binary_sensor.test_trend_sensor"))
    assert state.state == "on"
    assert state.attributes["sample_count"] == 3


async def test_non_numeric(hass: HomeAssistant):
    """Test for non-numeric sensor."""
    await _setup_component(hass, {"entity_id": "sensor.test_state"})

    hass.states.async_set("sensor.test_state", "Non")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "Numeric")
    await hass.async_block_till_done()

    assert (state := hass.states.get("binary_sensor.test_trend_sensor"))
    assert state.state == STATE_UNKNOWN


async def test_missing_attribute(hass: HomeAssistant):
    """Test for missing attribute."""
    await _setup_component(
        hass,
        {
            "entity_id": "sensor.test_state",
            "attribute": "missing",
        },
    )

    hass.states.async_set("sensor.test_state", "State", {"attr": "2"})
    await hass.async_block_till_done()
    hass.states.async_set("sensor.test_state", "State", {"attr": "1"})
    await hass.async_block_till_done()

    assert (state := hass.states.get("binary_sensor.test_trend_sensor"))
    assert state.state == STATE_UNKNOWN


async def test_invalid_name_does_not_create(hass: HomeAssistant):
    """Test for invalid name."""
    with assert_setup_component(0):
        assert await setup.async_setup_component(
            hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "trend",
                    "sensors": {
                        "test INVALID sensor": {"entity_id": "sensor.test_state"}
                    },
                }
            },
        )
    assert hass.states.async_all("binary_sensor") == []


async def test_invalid_sensor_does_not_create(hass: HomeAssistant):
    """Test invalid sensor."""
    with assert_setup_component(0):
        assert await setup.async_setup_component(
            hass,
            "binary_sensor",
            {
                "binary_sensor": {
                    "platform": "trend",
                    "sensors": {
                        "test_trend_sensor": {"not_entity_id": "sensor.test_state"}
                    },
                }
            },
        )
    assert hass.states.async_all("binary_sensor") == []


async def test_no_sensors_does_not_create(hass: HomeAssistant):
    """Test no sensors."""
    with assert_setup_component(0):
        assert await setup.async_setup_component(
            hass, "binary_sensor", {"binary_sensor": {"platform": "trend"}}
        )
    assert hass.states.async_all("binary_sensor") == []


async def test_reload(hass: HomeAssistant) -> None:
    """Verify we can reload trend sensors."""
    hass.states.async_set("sensor.test_state", 1234)

    await setup.async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "trend",
                "sensors": {"test_trend_sensor": {"entity_id": "sensor.test_state"}},
            }
        },
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("binary_sensor.test_trend_sensor")

    yaml_path = get_fixture_path("configuration.yaml", "trend")
    with patch.object(hass_config, "YAML_CONFIG_FILE", yaml_path):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 2

    assert hass.states.get("binary_sensor.test_trend_sensor") is None
    assert hass.states.get("binary_sensor.second_test_trend_sensor")


@pytest.mark.parametrize(
    ("saved_state", "restored_state"),
    [("on", "on"), ("off", "off"), ("unknown", "unknown")],
)
async def test_restore_state(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    saved_state: str,
    restored_state: str,
) -> None:
    """Test we restore the trend state."""
    mock_restore_cache(hass, (State("binary_sensor.test_trend_sensor", saved_state),))

    await _setup_component(
        hass,
        {
            "entity_id": "sensor.test_state",
            "sample_duration": 10000,
            "min_gradient": 1,
            "max_samples": 25,
            "min_samples": 5,
        },
    )

    # restored sensor should match saved one
    assert hass.states.get("binary_sensor.test_trend_sensor").state == restored_state

    # add not enough samples to trigger calculation
    for val in [10, 20, 30, 40]:
        freezer.tick(timedelta(seconds=2))
        hass.states.async_set("sensor.test_state", val)
        await hass.async_block_till_done()

    # state should match restored state as no calculation happened
    assert hass.states.get("binary_sensor.test_trend_sensor").state == restored_state

    # add more samples to trigger calculation
    for val in [50, 60, 70, 80]:
        freezer.tick(timedelta(seconds=2))
        hass.states.async_set("sensor.test_state", val)
        await hass.async_block_till_done()

    # sensor should detect an upwards trend and turn on
    assert hass.states.get("binary_sensor.test_trend_sensor").state == "on"


async def test_invalid_min_sample(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test if error is logged when min_sample is larger than max_samples."""
    with caplog.at_level(logging.ERROR):
        await _setup_component(
            hass,
            {
                "entity_id": "sensor.test_state",
                "max_samples": 25,
                "min_samples": 30,
            },
        )

    record = caplog.records[0]
    assert record.levelname == "ERROR"
    assert (
        "Invalid config for 'binary_sensor' from integration 'trend': min_samples must "
        "be smaller than or equal to max_samples" in record.message
    )
