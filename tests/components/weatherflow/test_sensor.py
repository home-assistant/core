"""Tests for the WeatherFlow sensor platform."""

import json
from unittest.mock import patch

import pytest
from pyweatherflowudp.aioudp import LocalEndpoint
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import ATTR_LAST_RESET
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from . import HUB_ADDRESS, setup_integration

from tests.common import (
    MockConfigEntry,
    load_fixture_bytes,
    load_json_object_fixture,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)

LAST_STRIKE_DISTANCE = "sensor.st_00000001_lightning_last_distance"
LAST_STRIKE_ENERGY = "sensor.st_00000001_lightning_last_energy"
LAST_STRIKE_TIME = "sensor.st_00000001_lightning_last_strike"
LIGHTNING_COUNT = "sensor.st_00000001_lightning_count"
RAIN_LAST_MINUTE = "sensor.st_00000001_precipitation"
STATION_PRESSURE = "sensor.st_00000001_air_pressure"
VAPOR_PRESSURE = "sensor.st_00000001_vapor_pressure"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_udp_endpoint: LocalEndpoint,
) -> None:
    """Test all sensor entities."""
    with patch("homeassistant.components.weatherflow.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry, mock_udp_endpoint)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("unit_system", "entity_id", "unit"),
    [
        pytest.param(METRIC_SYSTEM, STATION_PRESSURE, "hPa", id="metric-pressure"),
        pytest.param(METRIC_SYSTEM, VAPOR_PRESSURE, "hPa", id="metric-vapor"),
        pytest.param(METRIC_SYSTEM, RAIN_LAST_MINUTE, "mm", id="metric-rain"),
        pytest.param(US_CUSTOMARY_SYSTEM, STATION_PRESSURE, "inHg", id="us-pressure"),
        pytest.param(US_CUSTOMARY_SYSTEM, VAPOR_PRESSURE, "inHg", id="us-vapor"),
        pytest.param(US_CUSTOMARY_SYSTEM, RAIN_LAST_MINUTE, "in", id="us-rain"),
    ],
)
async def test_unit_system(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_endpoint: LocalEndpoint,
    unit_system: UnitSystem,
    entity_id: str,
    unit: str,
) -> None:
    """Test sensors are shown in the units of the configured unit system."""
    hass.config.units = unit_system
    await setup_integration(hass, mock_config_entry, mock_udp_endpoint)

    assert hass.states.get(entity_id).attributes[ATTR_UNIT_OF_MEASUREMENT] == unit


async def test_last_reset_only_advances_after_accumulation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_endpoint: LocalEndpoint,
) -> None:
    """Test last_reset only changes when the previous report accumulated."""

    def feed_observation(epoch: int, rain: float, strikes: int = 0) -> None:
        data = load_json_object_fixture("obs_st.json", "weatherflow")
        data["obs"][0][0] = epoch
        data["obs"][0][12] = rain
        data["obs"][0][15] = strikes
        mock_udp_endpoint.feed_datagram(json.dumps(data).encode(), HUB_ADDRESS)

    # The setup observation reports 0.12 mm of rain at epoch 1510855980.
    await setup_integration(hass, mock_config_entry, mock_udp_endpoint)

    state = hass.states.get(RAIN_LAST_MINUTE)
    assert state.state == "0.12"
    assert state.attributes[ATTR_LAST_RESET] == "2017-11-16T18:13:00+00:00"
    assert (
        hass.states.get(LIGHTNING_COUNT).attributes[ATTR_LAST_RESET]
        == "2017-11-16T18:13:00+00:00"
    )

    # The previous report accumulated rain, so this report starts a new cycle.
    feed_observation(1510856040, 0)
    await hass.async_block_till_done()
    state = hass.states.get(RAIN_LAST_MINUTE)
    assert state.state == "0"
    assert state.attributes[ATTR_LAST_RESET] == "2017-11-16T18:14:00+00:00"

    # Nothing accumulated since, so a run of empty reports keeps the cycle.
    feed_observation(1510856100, 0)
    await hass.async_block_till_done()
    state = hass.states.get(RAIN_LAST_MINUTE)
    assert state.attributes[ATTR_LAST_RESET] == "2017-11-16T18:14:00+00:00"
    feed_observation(1510856160, 0.5)
    await hass.async_block_till_done()
    state = hass.states.get(RAIN_LAST_MINUTE)
    assert state.state == "0.5"
    assert state.attributes[ATTR_LAST_RESET] == "2017-11-16T18:14:00+00:00"

    # The 0.5 mm report is flushed into statistics by the next report's reset.
    feed_observation(1510856220, 0)
    await hass.async_block_till_done()
    state = hass.states.get(RAIN_LAST_MINUTE)
    assert state.attributes[ATTR_LAST_RESET] == "2017-11-16T18:17:00+00:00"

    # A sensor that never accumulates keeps its initial last_reset.
    assert (
        hass.states.get(LIGHTNING_COUNT).attributes[ATTR_LAST_RESET]
        == "2017-11-16T18:13:00+00:00"
    )


async def test_last_strike_restored_until_next_strike(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_endpoint: LocalEndpoint,
) -> None:
    """Test the last strike is restored after a restart until a new strike."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(LAST_STRIKE_DISTANCE, "5"),
                {"native_value": 5, "native_unit_of_measurement": "km"},
            ),
            (
                State(LAST_STRIKE_ENERGY, "1234"),
                {"native_value": 1234, "native_unit_of_measurement": None},
            ),
            (
                State(LAST_STRIKE_TIME, "2026-09-23T23:13:10+00:00"),
                {
                    "native_value": {
                        "__type": "<class 'datetime.datetime'>",
                        "isoformat": "2026-09-23T23:13:10+00:00",
                    },
                    "native_unit_of_measurement": None,
                },
            ),
        ],
    )
    await setup_integration(hass, mock_config_entry, mock_udp_endpoint)

    assert hass.states.get(LAST_STRIKE_DISTANCE).state == "5"
    assert hass.states.get(LAST_STRIKE_ENERGY).state == "1234"
    assert hass.states.get(LAST_STRIKE_TIME).state == "2026-09-23T23:13:10+00:00"

    mock_udp_endpoint.feed_datagram(
        load_fixture_bytes("evt_strike.json", "weatherflow"), HUB_ADDRESS
    )
    await hass.async_block_till_done()

    assert hass.states.get(LAST_STRIKE_DISTANCE).state == "27"
    assert hass.states.get(LAST_STRIKE_ENERGY).state == "3848"
    assert hass.states.get(LAST_STRIKE_TIME).state == "2017-11-16T18:13:10+00:00"


async def test_last_strike_out_of_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_endpoint: LocalEndpoint,
) -> None:
    """Test the last distance is unknown when the strike is out of range."""
    await setup_integration(hass, mock_config_entry, mock_udp_endpoint)

    mock_udp_endpoint.feed_datagram(
        load_fixture_bytes("evt_strike_out_of_range.json", "weatherflow"), HUB_ADDRESS
    )
    await hass.async_block_till_done()

    assert hass.states.get(LAST_STRIKE_DISTANCE).state == STATE_UNKNOWN
    assert hass.states.get(LAST_STRIKE_ENERGY).state == "3848"


async def test_last_strike_out_of_range_not_restored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_endpoint: LocalEndpoint,
) -> None:
    """Test a strike cached before the sensors are added isn't replaced on restore."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(LAST_STRIKE_DISTANCE, "5"),
                {"native_value": 5, "native_unit_of_measurement": "km"},
            ),
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # The sensors are added once the device status and an observation have arrived.
    for fixture in ("evt_strike_out_of_range.json", "device.json", "obs_st.json"):
        mock_udp_endpoint.feed_datagram(
            load_fixture_bytes(fixture, "weatherflow"), HUB_ADDRESS
        )
    await hass.async_block_till_done()

    assert hass.states.get(LAST_STRIKE_DISTANCE).state == STATE_UNKNOWN
    assert hass.states.get(LAST_STRIKE_ENERGY).state == "3848"
