"""The tests for the derivative sensor platform."""
from datetime import timedelta
from math import sin
import random
from unittest.mock import patch

from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util


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
    with patch("homeassistant.util.dt.utcnow") as now:
        now.return_value = base
        hass.states.async_set(entity_id, 1, {})
        await hass.async_block_till_done()

        now.return_value += timedelta(seconds=3600)
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


async def setup_tests(hass, config, times, values, expected_state):
    """Test derivative sensor state."""
    config, entity_id = await _setup_sensor(hass, config)

    # Testing a energy sensor with non-monotonic intervals and values
    base = dt_util.utcnow()
    with patch("homeassistant.util.dt.utcnow") as now:
        for time, value in zip(times, values):
            now.return_value = base + timedelta(seconds=time)
            hass.states.async_set(entity_id, value, {}, force_update=True)
            await hass.async_block_till_done()

    state = hass.states.get("sensor.power")
    assert state is not None

    assert round(float(state.state), config["sensor"]["round"]) == expected_state
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.MEASUREMENT

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
    for time, value in zip(times, temperature_values):
        now = base + timedelta(seconds=time)
        with patch("homeassistant.util.dt.utcnow", return_value=now):
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
    for time, value in zip(times, temperature_values):
        now = base + timedelta(seconds=time)
        with patch("homeassistant.util.dt.utcnow", return_value=now):
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
    for time, value in zip(times, temperature_values):
        now = base + timedelta(seconds=time)
        with patch("homeassistant.util.dt.utcnow", return_value=now):
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
    with patch("homeassistant.util.dt.utcnow") as now:
        now.return_value = base
        hass.states.async_set(
            entity_id,
            1000,
            {"unit_of_measurement": UnitOfPower.WATT},
            force_update=True,
        )
        await hass.async_block_till_done()

        now.return_value += timedelta(seconds=3600)
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
    with patch("homeassistant.util.dt.utcnow") as now:
        now.return_value = base
        hass.states.async_set(entity_id, 1000, {})
        await hass.async_block_till_done()

        now.return_value += timedelta(seconds=10)
        hass.states.async_set(entity_id, 1000, {}, force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.derivative")
    assert state is not None

    # Testing a network speed sensor at 1000 bytes/s over 10s  = 10kbytes/s2
    assert round(float(state.state), config["sensor"]["round"]) == 0.0
