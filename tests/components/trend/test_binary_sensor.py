"""The test for the Trend sensor platform."""

from datetime import timedelta
import logging
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant import setup
from homeassistant.components.trend.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import ComponentSetup

from tests.common import MockConfigEntry, assert_setup_component, mock_restore_cache


async def _setup_legacy_component(hass: HomeAssistant, params: dict[str, Any]) -> None:
    """Set up the trend component the legacy way."""
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
async def test_basic_trend_setup_from_yaml(
    hass: HomeAssistant,
    states: list[str],
    inverted: bool,
    expected_state: str,
) -> None:
    """Test trend with a basic setup."""
    await _setup_legacy_component(
        hass,
        {
            "friendly_name": "Test state",
            "entity_id": "sensor.cpu_temp",
            "invert": inverted,
            "max_samples": 2.0,
            "min_gradient": 0.0,
            "sample_duration": 0.0,
        },
    )

    for state in states:
        hass.states.async_set("sensor.cpu_temp", state)
        await hass.async_block_till_done()

    assert (sensor_state := hass.states.get("binary_sensor.test_trend_sensor"))
    assert sensor_state.state == expected_state


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
    config_entry: MockConfigEntry,
    setup_component: ComponentSetup,
    states: list[str],
    inverted: bool,
    expected_state: str,
) -> None:
    """Test trend with a basic setup."""
    await setup_component(
        {
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
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    setup_component: ComponentSetup,
    state_series: list[list[str]],
    inverted: bool,
    expected_states: list[str],
) -> None:
    """Test uptrend using multiple samples and trendline calculation."""
    await setup_component(
        {
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
    config_entry: MockConfigEntry,
    setup_component: ComponentSetup,
    attr_values: list[str],
    expected_state: str,
) -> None:
    """Test attribute uptrend."""
    await setup_component(
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


async def test_max_samples(
    hass: HomeAssistant, config_entry: MockConfigEntry, setup_component: ComponentSetup
) -> None:
    """Test that sample count is limited correctly."""
    await setup_component(
        {
            "max_samples": 3,
            "min_gradient": -1,
        },
    )

    for val in (0, 1, 2, 3, 2, 1):
        hass.states.async_set("sensor.test_state", val)
        await hass.async_block_till_done()

    assert (state := hass.states.get("binary_sensor.test_trend_sensor"))
    assert state.state == "on"
    assert state.attributes["sample_count"] == 3


async def test_non_numeric(
    hass: HomeAssistant, config_entry: MockConfigEntry, setup_component: ComponentSetup
) -> None:
    """Test for non-numeric sensor."""
    await setup_component({"entity_id": "sensor.test_state"})

    for val in ("Non", "Numeric"):
        hass.states.async_set("sensor.test_state", val)
        await hass.async_block_till_done()

    assert (state := hass.states.get("binary_sensor.test_trend_sensor"))
    assert state.state == STATE_UNKNOWN


async def test_missing_attribute(
    hass: HomeAssistant, config_entry: MockConfigEntry, setup_component: ComponentSetup
) -> None:
    """Test for missing attribute."""
    await setup_component(
        {
            "attribute": "missing",
        },
    )

    for val in (1, 2):
        hass.states.async_set("sensor.test_state", "State", {"attr": val})
        await hass.async_block_till_done()

    assert (state := hass.states.get("binary_sensor.test_trend_sensor"))
    assert state.state == STATE_UNKNOWN


async def test_invalid_name_does_not_create(hass: HomeAssistant) -> None:
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


async def test_invalid_sensor_does_not_create(hass: HomeAssistant) -> None:
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


async def test_no_sensors_does_not_create(hass: HomeAssistant) -> None:
    """Test no sensors."""
    with assert_setup_component(0):
        assert await setup.async_setup_component(
            hass, "binary_sensor", {"binary_sensor": {"platform": "trend"}}
        )
    assert hass.states.async_all("binary_sensor") == []


@pytest.mark.parametrize(
    ("saved_state", "restored_state"),
    [("on", "on"), ("off", "off"), ("unknown", "unknown")],
)
async def test_restore_state(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    setup_component: ComponentSetup,
    saved_state: str,
    restored_state: str,
) -> None:
    """Test we restore the trend state."""
    mock_restore_cache(hass, (State("binary_sensor.test_trend_sensor", saved_state),))

    await setup_component(
        {
            "sample_duration": 10000,
            "min_gradient": 1,
            "max_samples": 25,
            "min_samples": 5,
        },
    )

    # restored sensor should match saved one
    assert hass.states.get("binary_sensor.test_trend_sensor").state == restored_state

    # add not enough samples to trigger calculation
    for val in (10, 20, 30, 40):
        freezer.tick(timedelta(seconds=2))
        hass.states.async_set("sensor.test_state", val)
        await hass.async_block_till_done()

    # state should match restored state as no calculation happened
    assert hass.states.get("binary_sensor.test_trend_sensor").state == restored_state

    # add more samples to trigger calculation
    for val in (50, 60, 70, 80):
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
        await _setup_legacy_component(
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


async def test_device_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test for source entity device for Trend."""
    source_config_entry = MockConfigEntry()
    source_config_entry.add_to_hass(hass)
    source_device_entry = device_registry.async_get_or_create(
        config_entry_id=source_config_entry.entry_id,
        identifiers={("sensor", "identifier_test")},
        connections={("mac", "30:31:32:33:34:35")},
    )
    source_entity = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "source",
        config_entry=source_config_entry,
        device_id=source_device_entry.id,
    )
    await hass.async_block_till_done()
    assert entity_registry.async_get("sensor.test_source") is not None

    trend_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "Trend",
            "entity_id": "sensor.test_source",
            "invert": False,
        },
        title="Trend",
    )
    trend_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(trend_config_entry.entry_id)
    await hass.async_block_till_done()

    trend_entity = entity_registry.async_get("binary_sensor.trend")
    assert trend_entity is not None
    assert trend_entity.device_id == source_entity.device_id
