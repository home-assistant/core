"""The tests for the derivative sensor platform."""
from datetime import timedelta
import logging
from math import sin

from freezegun import freeze_time

from homeassistant.components.derivative.const import DOMAIN
from homeassistant.components.derivative.sensor import _LOGGER as derivative_logger
from homeassistant.const import UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_state(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    config = {
        "sensor": {
            "platform": "derivative",
            "name": "derivative",
            "source": "sensor.energy",
            "unit": "kW",
            "round": 2,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    base = dt_util.utcnow()
    with freeze_time(base) as freezer:
        hass.states.async_set(entity_id, 1, {})
        await hass.async_block_till_done()

        freezer.move_to(dt_util.utcnow() + timedelta(seconds=3600))
        hass.states.async_set(entity_id, 1, {}, force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.derivative")
    assert state is not None

    # Testing a energy sensor at 1 kWh for 1hour = 0kW
    assert round(float(state.state), config["sensor"]["round"]) == 0.0

    assert state.attributes.get("unit_of_measurement") == "kW"


async def _setup_sensor(hass, config):
    default_config = {
        "platform": "derivative",
        "name": "power",
        "source": "sensor.energy",
        "round": 2,
    }

    config = {"sensor": dict(default_config, **config)}
    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(entity_id, 0, {})
    await hass.async_block_till_done()

    return config, entity_id


async def setup_tests(
    hass: HomeAssistant, config, times, values, force_update, expected_state
):
    """Test derivative sensor state."""

    # Set derivative logger to DEBUG level for debugging failed tests.
    derivative_logger.setLevel(logging.DEBUG)

    assert len(times) == len(values)

    config, entity_id = await _setup_sensor(hass, config)

    # Testing a energy sensor with non-monotonic intervals and values. Set the base time to the next rounded second.
    base = (dt_util.utcnow() + timedelta(seconds=1)).replace(microsecond=0)

    with freeze_time(base) as freezer:
        for time, value in zip(times, values):
            new_time = base + timedelta(seconds=time)
            logging.getLogger().info(
                f"Move test time to {new_time} ({time} seconds after test start) with value {value}"
            )
            freezer.move_to(new_time)
            async_fire_time_changed(hass, new_time)
            if value is not None:
                hass.states.async_set(entity_id, value, {}, force_update=force_update)
            await hass.async_block_till_done()

    state = hass.states.get("sensor.power")
    assert state is not None

    assert round(float(state.state), config["sensor"]["round"]) == expected_state

    return state


async def test_dataSet0(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    # With only 1 state (change) the derivative is 0
    await setup_tests(
        hass,
        {"unit_time": UnitOfTime.SECONDS},
        times=[20],
        values=[5],
        force_update=False,
        expected_state=0.0,
    )


async def test_dataSet1(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    await setup_tests(
        hass,
        {"unit_time": UnitOfTime.SECONDS},
        times=[20, 30, 40, 50],
        values=[10, 30, 5, 0],
        force_update=False,
        expected_state=-0.5,
    )


async def test_dataSet2(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    await setup_tests(
        hass,
        {"unit_time": UnitOfTime.SECONDS},
        times=[20, 30],
        values=[5, 0],
        force_update=False,
        expected_state=-0.5,
    )


async def test_dataSet3(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    state = await setup_tests(
        hass,
        {"unit_time": UnitOfTime.SECONDS},
        times=[20, 30],
        values=[5, 10],
        force_update=False,
        expected_state=0.5,
    )

    assert state.attributes.get("unit_of_measurement") == f"/{UnitOfTime.SECONDS}"


async def test_dataSet4(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""

    await setup_tests(
        hass,
        {"unit_time": UnitOfTime.SECONDS},
        times=[10, 20, 30],
        values=[1, 5, 5],
        force_update=True,  # Force because the values are the same, and then derivative is 0
        expected_state=0,
    )


async def test_dataSet4_no_force(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    await setup_tests(
        hass,
        {"unit_time": UnitOfTime.SECONDS},
        times=[10, 20, 30],
        values=[1, 5, 5],
        force_update=False,  # Without force the value stays as it was: 0.4
        expected_state=0.4,
    )


async def test_dataSet5(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    await setup_tests(
        hass,
        {"unit_time": UnitOfTime.SECONDS},
        times=[20, 30],
        values=[10, -10],
        force_update=False,
        expected_state=-2,
    )


async def test_dataSet6(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    await setup_tests(
        hass,
        {},
        times=[0, 60],
        values=[0, 1 / 60],
        force_update=True,
        expected_state=1,
    )


async def test_SMA_dataSet1(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    # If the first state (change) has not yet left the time window, the algorithm assumes this value has been the state for all of history.
    # Therefore at time 6 (with value 20) the value at the other end of the time window (-4) is 10 (which was actually received at time 0), resulting in derivative (20-10)/10 = 1
    await setup_tests(
        hass,
        {"time_window": 10, "unit_time": UnitOfTime.SECONDS},
        times=[0, 6],
        values=[10, 20],
        force_update=False,
        expected_state=1,
    )


async def test_SMA_dataSet1_wait_done(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    # When the last state change has left the window, the derivative should be reset to 0.
    await setup_tests(
        hass,
        {"time_window": 10, "unit_time": UnitOfTime.SECONDS},
        times=[0, 6, 17],
        values=[10, 20, None],
        force_update=False,
        expected_state=0,
    )


async def test_SMA_dataSet2(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    # Intermediate values don't matter, only the values at the end points.
    # So extremely large values in the middle of the time_window are not relevant at time 6,
    # but they were relevant when they occurred (entered the time window) and will be again when they leave it.
    await setup_tests(
        hass,
        {"time_window": 10, "unit_time": UnitOfTime.SECONDS},
        times=[0, 1, 2, 3, 4, 5, 6],
        values=[10, 100000, 200000, 300000, 400000, 500000, 20],
        force_update=False,
        expected_state=1,
    )


async def test_SMA_dataSet3(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    await setup_tests(
        hass,
        {"time_window": 10, "unit_time": UnitOfTime.SECONDS},
        times=[0, 1, 2, 3, 4, 5, 6, 11.5],
        values=[10, 100000, 200000, 300000, 400000, 500000, 20, -1],
        force_update=False,
        expected_state=-10000.1,
    )


async def test_SMA_dataSet4(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    await setup_tests(
        hass,
        {"time_window": 10, "unit_time": UnitOfTime.SECONDS},
        times=[0, 1, 2, 3, 4, 5, 6, 11.5, 12.5],
        values=[10, 100000, 200000, 300000, 400000, 500000, 20, -1, None],
        force_update=False,
        expected_state=-20000.1,
    )


async def test_SMA_dataSet5(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    await setup_tests(
        hass,
        {"time_window": 10, "unit_time": UnitOfTime.SECONDS},
        times=[0, 1, 2, 3, 4, 5, 6, 11.5, 12.5, 15.5],
        values=[10, 100000, 200000, 300000, 400000, 500000, 20, -1, None, None],
        force_update=False,
        expected_state=-50000.1,
    )


async def test_SMA_dataSet6(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    # Wait until the last value has left the window, and see that the derivative is 0 again, even with many values in the window.
    await setup_tests(
        hass,
        {"time_window": 10, "unit_time": UnitOfTime.SECONDS},
        times=[0, 1, 2, 3, 4, 5, 6, 11.5, 12.5, 15.5, 22],
        values=[10, 100000, 200000, 300000, 400000, 500000, 20, -1, None, None, None],
        force_update=False,
        expected_state=0.0,
    )


async def test_double_signal_after_delay(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    # The old algorithm would produce extreme values if, after a delay longer than the time window
    # there would be two signals, a large spike would be produced. Check explicitly for this situation
    time_window = 60
    times = [*range(time_window * 10)]
    times = times + [
        time_window * 20,
        time_window * 20 + 0.01,
    ]

    # just apply sine as some sort of temperature change and make sure the change after the delay is very small
    temperature_values = [sin(x) for x in times]
    temperature_values[-2] = temperature_values[-3] + 0.01
    temperature_values[-1] = temperature_values[-2] + 0.01

    config, entity_id = await _setup_sensor(
        hass,
        {
            "time_window": {"seconds": time_window},
            "unit_time": UnitOfTime.MINUTES,
            "round": 3,
        },
    )

    base = dt_util.utcnow()
    previous = 0
    with freeze_time(base) as freezer:
        for time, value in zip(times, temperature_values):
            now = base + timedelta(seconds=time)
            freezer.move_to(now)
            hass.states.async_set(entity_id, value, {}, force_update=True)
            await hass.async_block_till_done()
            state = hass.states.get("sensor.power")
            derivative = round(float(state.state), config["sensor"]["round"])
            if time == times[-1]:
                # Test that the error is never more than
                # (time_window_in_minutes / true_derivative * 100) = 10% + ε
                assert abs(previous - derivative) <= 0.01 + 1e-6
            previous = derivative


async def test_prefix(hass: HomeAssistant) -> None:
    """Test derivative sensor state using a power source."""
    config = {
        "sensor": {
            "platform": "derivative",
            "name": "derivative",
            "source": "sensor.power",
            "round": 2,
            "unit_prefix": "k",
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    base = dt_util.utcnow()
    with freeze_time(base) as freezer:
        hass.states.async_set(
            entity_id,
            1000,
            {"unit_of_measurement": UnitOfPower.WATT},
            force_update=True,
        )
        await hass.async_block_till_done()

        freezer.move_to(dt_util.utcnow() + timedelta(seconds=3600))
        hass.states.async_set(
            entity_id,
            1000,
            {"unit_of_measurement": UnitOfPower.WATT},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.derivative")
    assert state is not None

    # Testing a power sensor at 1000 Watts for 1hour = 0kW/h
    assert round(float(state.state), config["sensor"]["round"]) == 0.0
    assert state.attributes.get("unit_of_measurement") == f"kW/{UnitOfTime.HOURS}"


async def test_suffix(hass: HomeAssistant) -> None:
    """Test derivative sensor state using a network counter source."""
    config = {
        "sensor": {
            "platform": "derivative",
            "name": "derivative",
            "source": "sensor.bytes_per_second",
            "round": 2,
            "unit_prefix": "k",
            "unit_time": UnitOfTime.SECONDS,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    base = dt_util.utcnow()
    with freeze_time(base) as freezer:
        hass.states.async_set(entity_id, 1000, {})
        await hass.async_block_till_done()

        freezer.move_to(dt_util.utcnow() + timedelta(seconds=3600))
        hass.states.async_set(entity_id, 1000, {}, force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.derivative")
    assert state is not None

    # Testing a network speed sensor at 1000 bytes/s over 10s  = 10kbytes/s2
    assert round(float(state.state), config["sensor"]["round"]) == 0.0


async def test_device_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test for source entity device for Derivative."""
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

    derivative_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "Derivative",
            "round": 1.0,
            "source": "sensor.test_source",
            "time_window": {"seconds": 0.0},
            "unit_prefix": "k",
            "unit_time": "min",
        },
        title="Derivative",
    )

    derivative_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(derivative_config_entry.entry_id)
    await hass.async_block_till_done()

    derivative_entity = entity_registry.async_get("sensor.derivative")
    assert derivative_entity is not None
    assert derivative_entity.device_id == source_entity.device_id
