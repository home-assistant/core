"""The tests for the derivative sensor platform."""

from datetime import timedelta
from math import sin
import random
from typing import Any

from freezegun import freeze_time

from homeassistant.components.derivative.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry


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


async def _setup_sensor(
    hass: HomeAssistant, config: dict[str, Any]
) -> tuple[dict[str, Any], str]:
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
    hass: HomeAssistant,
    config: dict[str, Any],
    times: list[int],
    values: list[float],
    expected_state: float,
) -> State:
    """Test derivative sensor state."""
    config, entity_id = await _setup_sensor(hass, config)

    # Testing a energy sensor with non-monotonic intervals and values
    base = dt_util.utcnow()
    with freeze_time(base) as freezer:
        for time, value in zip(times, values, strict=False):
            freezer.move_to(base + timedelta(seconds=time))
            hass.states.async_set(entity_id, value, {}, force_update=True)
            await hass.async_block_till_done()

    state = hass.states.get("sensor.power")
    assert state is not None

    assert round(float(state.state), config["sensor"]["round"]) == expected_state

    return state


async def test_dataSet1(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    await setup_tests(
        hass,
        {"unit_time": UnitOfTime.SECONDS},
        times=[20, 30, 40, 50],
        values=[10, 30, 5, 0],
        expected_state=-0.5,
    )


async def test_dataSet2(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    await setup_tests(
        hass,
        {"unit_time": UnitOfTime.SECONDS},
        times=[20, 30],
        values=[5, 0],
        expected_state=-0.5,
    )


async def test_dataSet3(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    state = await setup_tests(
        hass,
        {"unit_time": UnitOfTime.SECONDS},
        times=[20, 30],
        values=[5, 10],
        expected_state=0.5,
    )

    assert state.attributes.get("unit_of_measurement") == f"/{UnitOfTime.SECONDS}"


async def test_dataSet4(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    await setup_tests(
        hass,
        {"unit_time": UnitOfTime.SECONDS},
        times=[20, 30],
        values=[5, 5],
        expected_state=0,
    )


async def test_dataSet5(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    await setup_tests(
        hass,
        {"unit_time": UnitOfTime.SECONDS},
        times=[20, 30],
        values=[10, -10],
        expected_state=-2,
    )


async def test_dataSet6(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    await setup_tests(hass, {}, times=[0, 60], values=[0, 1 / 60], expected_state=1)


async def test_data_moving_average_for_discrete_sensor(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    # We simulate the following situation:
    # The temperature rises 1 °C per minute for 30 minutes long.
    # There is a data point every 30 seconds, however, the sensor returns
    # the temperature rounded down to an integer value.
    # We use a time window of 10 minutes and therefore we can expect
    # (because the true derivative is 1 °C/min) an error of less than 10%.

    temperature_values = []
    for temperature in range(30):
        temperature_values += [temperature] * 2  # two values per minute
    time_window = 600
    times = list(range(0, 1800 + 30, 30))

    config, entity_id = await _setup_sensor(
        hass,
        {
            "time_window": {"seconds": time_window},
            "unit_time": UnitOfTime.MINUTES,
            "round": 1,
        },
    )  # two minute window

    base = dt_util.utcnow()
    with freeze_time(base) as freezer:
        for time, value in zip(times, temperature_values, strict=False):
            now = base + timedelta(seconds=time)
            freezer.move_to(now)
            hass.states.async_set(entity_id, value, {}, force_update=True)
            await hass.async_block_till_done()

            if time_window < time < times[-1] - time_window:
                state = hass.states.get("sensor.power")
                derivative = round(float(state.state), config["sensor"]["round"])
                # Test that the error is never more than
                # (time_window_in_minutes / true_derivative * 100) = 10% + ε
                assert abs(1 - derivative) <= 0.1 + 1e-6


async def test_data_moving_average_for_irregular_times(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    # We simulate the following situation:
    # The temperature rises 1 °C per minute for 30 minutes long.
    # There is 60 random datapoints (and the start and end) and the signal is normally distributed
    # around the expected value with ±0.1°C
    # We use a time window of 1 minute and expect an error of less than the standard deviation. (0.01)

    time_window = 60
    random.seed(0)
    times = sorted(random.sample(range(1800), 60))

    def temp_function(time):
        random.seed(0)
        temp = time / (600)
        return random.gauss(temp, 0.1)

    temperature_values = list(map(temp_function, times))

    config, entity_id = await _setup_sensor(
        hass,
        {
            "time_window": {"seconds": time_window},
            "unit_time": UnitOfTime.MINUTES,
            "round": 3,
        },
    )

    base = dt_util.utcnow()
    with freeze_time(base) as freezer:
        for time, value in zip(times, temperature_values, strict=False):
            now = base + timedelta(seconds=time)
            freezer.move_to(now)
            hass.states.async_set(entity_id, value, {}, force_update=True)
            await hass.async_block_till_done()

            if time_window < time and time > times[3]:
                state = hass.states.get("sensor.power")
                derivative = round(float(state.state), config["sensor"]["round"])
                # Test that the error is never more than
                # (time_window_in_minutes / true_derivative * 100) = 10% + ε
                assert abs(0.1 - derivative) <= 0.01 + 1e-6


async def test_double_signal_after_delay(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    # The old algorithm would produce extreme values if, after a delay longer than the time window
    # there would be two signals, a large spike would be produced. Check explicitly for this situation
    time_window = 60
    times = [*range(time_window * 10), time_window * 20, time_window * 20 + 0.01]

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
        for time, value in zip(times, temperature_values, strict=False):
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


async def test_total_increasing_reset(hass: HomeAssistant) -> None:
    """Test derivative sensor state with total_increasing sensor input where it should ignore the reset value."""
    times = [0, 20, 30, 35, 40, 50, 60]
    values = [0, 10, 30, 40, 0, 10, 40]
    expected_times = [0, 20, 30, 35, 50, 60]
    expected_values = ["0.00", "0.50", "2.00", "2.00", "1.00", "3.00"]

    config, entity_id = await _setup_sensor(hass, {"unit_time": UnitOfTime.SECONDS})

    base_time = dt_util.utcnow()
    actual_times = []
    actual_values = []
    with freeze_time(base_time) as freezer:
        for time, value in zip(times, values, strict=False):
            current_time = base_time + timedelta(seconds=time)
            freezer.move_to(current_time)
            hass.states.async_set(
                entity_id,
                value,
                {ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING},
                force_update=True,
            )
            await hass.async_block_till_done()

            state = hass.states.get("sensor.power")
            assert state is not None

            if state.last_reported == current_time:
                actual_times.append(time)
                actual_values.append(state.state)

    assert actual_times == expected_times
    assert actual_values == expected_values


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
