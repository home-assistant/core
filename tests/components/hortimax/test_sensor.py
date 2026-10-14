"""Test the Ridder HortiMaX Pro sensor platform."""

from datetime import UTC, datetime, timedelta
from math import inf, nan
from unittest.mock import AsyncMock

from aiohortos import HortosConnectionError, Readout, Source
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import load_readouts

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


def _sunrise_readout(value: float, sampled_at: datetime | None = None) -> Readout:
    """Build a SunriseToday readout, whose value is seconds since midnight."""
    return Readout(
        identifier="SunriseToday-Measured",
        name="Sunrise today",
        unit="Second",
        source=Source(name="Weather station 001", type="WeatherStation"),
        value=value,
        timestamp=sampled_at,
    )


@pytest.mark.freeze_time("2026-06-12 12:00:00+00:00")
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_hortos_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test all sensors of a controller."""
    await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_hortos_client")
async def test_unclassified_readouts_are_disabled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test readouts with no device class, icon or state class are disabled."""
    await setup_integration(hass, mock_config_entry)

    # An enumeration code nobody has decoded yet: no unit, no device class.
    weather_status = entity_registry.async_get("sensor.weerstation_weather_status")
    assert weather_status is not None
    assert weather_status.disabled_by is er.RegistryEntryDisabler.INTEGRATION

    # A classified readout right next to it stays enabled.
    temperature = entity_registry.async_get("sensor.weerstation_outside_temperature")
    assert temperature is not None
    assert temperature.disabled_by is None

    # A measurement Home Assistant has no device class for is still a
    # measurement, so it stays enabled on the strength of its state class.
    screen = entity_registry.async_get("sensor.ov1_tropen_screen_screen_position")
    assert screen is not None
    assert screen.disabled_by is None

    conductivity = entity_registry.async_get(
        "sensor.valve_group_003_substrate_conductivity"
    )
    assert conductivity is not None
    assert conductivity.disabled_by is None


@pytest.mark.usefixtures("mock_hortos_client")
async def test_ph_has_a_device_class_but_no_unit(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test pH gets its device class rather than a unit, since pH is dimensionless."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.valve_group_003_ph")
    assert state is not None
    assert state.state == "6.2"
    assert state.attributes[ATTR_DEVICE_CLASS] == SensorDeviceClass.PH
    assert ATTR_UNIT_OF_MEASUREMENT not in state.attributes


@pytest.mark.usefixtures("mock_hortos_client")
async def test_new_readouts_are_added(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a readout that only shows up later still becomes a sensor."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("sensor.weerstation_2_outside_temperature") is None

    mock_hortos_client.get_latest_readouts.return_value = [
        *load_readouts(),
        Readout(
            identifier="OutsideTemperature-Measured",
            name="Outside temperature (Weerstation 2)",
            unit="DegreeCelsius",
            source=Source(
                name="Weather station 002",
                type="WeatherStation",
                user_defined_name="Weerstation 2",
            ),
            value=19.5,
        ),
    ]

    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.weerstation_2_outside_temperature")
    assert state is not None
    assert state.state == "19.5"


@pytest.mark.usefixtures("mock_hortos_client")
async def test_update_failure_makes_entities_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities go unavailable when a poll fails."""
    await setup_integration(hass, mock_config_entry)
    assert (
        hass.states.get("sensor.weerstation_outside_temperature").state == "18.203125"
    )

    mock_hortos_client.get_latest_readouts.side_effect = HortosConnectionError("boom")
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.weerstation_outside_temperature").state
        == STATE_UNAVAILABLE
    )


@pytest.mark.usefixtures("mock_hortos_client")
async def test_disappearing_readout_becomes_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a readout the controller stops reporting is unknown, not unavailable."""
    await setup_integration(hass, mock_config_entry)

    mock_hortos_client.get_latest_readouts.return_value = [
        readout
        for readout in load_readouts()
        if readout.identifier != "OutsideTemperature-Measured"
    ]
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.weerstation_outside_temperature").state == STATE_UNKNOWN
    )


async def test_disappearing_device_becomes_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an entity whose controller drops out of a good poll is unavailable."""
    await setup_integration(hass, mock_config_entry)
    assert (
        hass.states.get("sensor.weerstation_outside_temperature").state == "18.203125"
    )

    mock_hortos_client.get_devices.return_value = []
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.weerstation_outside_temperature").state
        == STATE_UNAVAILABLE
    )


@pytest.mark.usefixtures("mock_hortos_client")
@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (8772, "0.0"),  # north, the anchor of the block
        (8783, "247.5"),  # WSW, cross-checked against the official app
        (8787, "337.5"),  # NNW, the last code of the block
        (8771, "unknown"),  # just below the block
        (8788, "unknown"),  # just above it
        (0, "unknown"),
        # Fractional values are not member ids; rounding them into the block
        # would report 8771.6 as due north.
        (8771.6, "unknown"),
        (8787.4, "unknown"),
        # The API sends doubles as strings for some readouts, which every
        # other sensor accepts.
        ("8783", "247.5"),
    ],
)
async def test_wind_direction_codes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
    code: float | str,
    expected: str,
) -> None:
    """Test only the documented enum block becomes a bearing."""
    mock_hortos_client.get_latest_readouts.return_value = [
        Readout(
            identifier="CardinalWindDirection-Measured",
            name="Cardinal wind direction",
            unit="Scalar",
            source=Source(name="Weather station 001", type="WeatherStation"),
            value=code,
        )
    ]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.weather_station_001_cardinal_wind_direction")
    assert state is not None
    assert state.state == expected


@pytest.mark.usefixtures("mock_hortos_client")
@pytest.mark.parametrize(
    "value",
    [
        pytest.param("n/a", id="text"),
        pytest.param(nan, id="nan"),
        pytest.param(inf, id="infinity"),
        pytest.param("NaN", id="nan_as_text"),
    ],
)
async def test_unusable_double_is_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
    value: float | str,
) -> None:
    """Test a numeric readout without a usable value is reported as unknown."""
    mock_hortos_client.get_latest_readouts.return_value = [
        Readout(
            identifier="OutsideTemperature-Measured",
            name="Outside temperature",
            unit="DegreeCelsius",
            source=Source(name="Weather station 001", type="WeatherStation"),
            value=value,
        )
    ]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.weather_station_001_outside_temperature")
    assert state is not None
    assert state.state == "unknown"


@pytest.mark.usefixtures("mock_hortos_client")
@pytest.mark.parametrize(
    "value",
    [
        pytest.param(nan, id="nan"),
        pytest.param(inf, id="infinity"),
        pytest.param(-1.0, id="before_midnight"),
        pytest.param(86400.0, id="end_of_day"),
        pytest.param(1e20, id="beyond_timedelta"),
    ],
)
async def test_time_of_day_outside_the_day_is_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
    value: float,
) -> None:
    """Test a time-of-day readout that is not a time of day never reaches timedelta()."""
    mock_hortos_client.get_latest_readouts.return_value = [_sunrise_readout(value)]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.weather_station_001_sunrise_today")
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("mock_hortos_client")
@pytest.mark.parametrize(
    ("now", "expected"),
    [
        pytest.param(
            "2026-06-18 21:59:00+00:00",
            "2026-06-18T03:19:05+00:00",
            id="before_midnight",
        ),
        pytest.param(
            "2026-06-18 22:01:00+00:00",
            "2026-06-19T03:19:05+00:00",
            id="after_midnight",
        ),
    ],
)
async def test_time_of_day_follows_the_local_day(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    now: str,
    expected: str,
) -> None:
    """Test the timestamp tracks the current local day, not when it was sampled.

    SunriseToday describes the controller's current day, so an unchanged value
    read either side of local midnight belongs to whichever day it is now. The
    readout is sampled well before midnight in both cases.
    """
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    freezer.move_to(now)
    mock_hortos_client.get_latest_readouts.return_value = [
        _sunrise_readout(19145.0, sampled_at=datetime(2026, 6, 18, 12, 0, tzinfo=UTC))
    ]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.weather_station_001_sunrise_today")
    assert state is not None
    assert state.state == expected


@pytest.mark.usefixtures("mock_hortos_client")
async def test_readout_without_a_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
) -> None:
    """Test a readout the API reports as null is unknown, not unavailable."""
    mock_hortos_client.get_latest_readouts.return_value = [
        Readout(
            identifier="OutsideTemperature-Measured",
            name="Outside temperature",
            unit="DegreeCelsius",
            source=Source(name="Weather station 001", type="WeatherStation"),
            value=None,
        )
    ]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.weather_station_001_outside_temperature")
    assert state is not None
    assert state.state == "unknown"
