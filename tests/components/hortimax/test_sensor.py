"""Test the Ridder HortiMaX Pro sensor platform."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aiohortos import HortosConnectionError, Readout, Source
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import load_readouts

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


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
    """Test readouts without a device class or icon are created disabled."""
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
async def test_disappearing_readout_becomes_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a readout the controller stops reporting goes unavailable."""
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
    ],
)
async def test_wind_direction_codes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
    code: int,
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
async def test_non_numeric_double_is_unknown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hortos_client: AsyncMock,
) -> None:
    """Test a numeric readout carrying text is reported as unknown."""
    mock_hortos_client.get_latest_readouts.return_value = [
        Readout(
            identifier="OutsideTemperature-Measured",
            name="Outside temperature",
            unit="DegreeCelsius",
            source=Source(name="Weather station 001", type="WeatherStation"),
            value="n/a",
        )
    ]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.weather_station_001_outside_temperature")
    assert state is not None
    assert state.state == "unknown"


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
