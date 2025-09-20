"""The tests for the derivative sensor platform."""

from datetime import timedelta
from math import sin
import random
from typing import Any

from freezegun import freeze_time
import pytest

from homeassistant.components.derivative.const import DOMAIN
from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorStateClass
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

A1 = {"attr": "value1"}
A2 = {"attr": "value2"}


@pytest.mark.parametrize("force_update", [False, True])
@pytest.mark.parametrize(
    "attributes",
    [
        # Same attributes, fires state report
        [A1, A1],
        # Changing attributes, fires state change with bumped last_updated
        [A1, A2],
    ],
)
async def test_state(
    hass: HomeAssistant,
    force_update: bool,
    attributes: list[dict[str, Any]],
) -> None:
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
        for extra_attributes in attributes:
            hass.states.async_set(
                entity_id, 1, extra_attributes, force_update=force_update
            )
            await hass.async_block_till_done()

            freezer.move_to(dt_util.utcnow() + timedelta(seconds=3600))

    state = hass.states.get("sensor.derivative")
    assert state is not None

    # Testing a energy sensor at 1 kWh for 1hour = 0kW
    assert round(float(state.state), config["sensor"]["round"]) == 0.0

    assert state.attributes.get("unit_of_measurement") == "kW"


# Test unchanged states work both with and without max_sub_interval
@pytest.mark.parametrize("extra_config", [{}, {"max_sub_interval": {"minutes": 9999}}])
@pytest.mark.parametrize("force_update", [False, True])
@pytest.mark.parametrize(
    "attributes",
    [
        # Same attributes, fires state report
        [A1, A1, A1, A1],
        # Changing attributes, fires state change with bumped last_updated
        [A1, A2, A1, A2],
    ],
)
async def test_no_change(
    hass: HomeAssistant,
    extra_config: dict[str, Any],
    force_update: bool,
    attributes: list[dict[str, Any]],
) -> None:
    """Test derivative sensor state updated when source sensor doesn't change."""
    events: list[Event[EventStateChangedData]] = []

    @callback
    def _capture_event(event: Event) -> None:
        events.append(event)

    async_track_state_change_event(hass, "sensor.derivative", _capture_event)

    config = {
        "sensor": {
            "platform": "derivative",
            "name": "derivative",
            "source": "sensor.energy",
            "unit": "kW",
            "round": 2,
        }
        | extra_config
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    entity_id = config["sensor"]["source"]
    base = dt_util.utcnow()
    with freeze_time(base) as freezer:
        for value, extra_attributes in zip([0, 1, 1, 1], attributes, strict=True):
            hass.states.async_set(
                entity_id, value, extra_attributes, force_update=force_update
            )
            await hass.async_block_till_done()

            freezer.move_to(dt_util.utcnow() + timedelta(seconds=3600))

    state = hass.states.get("sensor.derivative")
    assert state is not None

    await hass.async_block_till_done()
    await hass.async_block_till_done()
    states = [events[0].data["new_state"].state] + [
        round(float(event.data["new_state"].state), config["sensor"]["round"])
        for event in events[1:]
    ]
    # Testing a energy sensor at 1 kWh for 1hour = 0kW
    assert states == ["unavailable", 0.0, 1.0, 0.0]

    state = events[-1].data["new_state"]

    assert state.attributes.get("unit_of_measurement") == "kW"

    assert state.last_changed == base + timedelta(seconds=2 * 3600)


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
    await hass.async_block_till_done()

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
        for time, value in zip(times, values, strict=True):
            freezer.move_to(base + timedelta(seconds=time))
            hass.states.async_set(entity_id, value, {})
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


# Test unchanged states work both with and without max_sub_interval
@pytest.mark.parametrize("extra_config", [{}, {"max_sub_interval": {"minutes": 9999}}])
@pytest.mark.parametrize("force_update", [False, True])
@pytest.mark.parametrize(
    "attributes",
    [
        # Same attributes, fires state report
        [A1, A1] * 10 + [A1],
        # Changing attributes, fires state change with bumped last_updated
        [A1, A2] * 10 + [A1],
    ],
)
async def test_data_moving_average_with_zeroes(
    hass: HomeAssistant,
    extra_config: dict[str, Any],
    force_update: bool,
    attributes: list[dict[str, Any]],
) -> None:
    """Test that zeroes are properly handled within the time window."""
    # We simulate the following situation:
    # The temperature rises 1 °C per minute for 10 minutes long. Then, it
    # stays constant for another 10 minutes. There is a data point every
    # minute and we use a time window of 10 minutes.
    # Therefore, we can expect the derivative to peak at 1 after 10 minutes
    # and then fall down to 0 in steps of 10%.

    events: list[Event[EventStateChangedData]] = []

    @callback
    def _capture_event(event: Event) -> None:
        events.append(event)

    async_track_state_change_event(hass, "sensor.power", _capture_event)

    temperature_values = []
    for temperature in range(10):
        temperature_values += [temperature]
    temperature_values += [10] * 11
    time_window = 600
    times = list(range(0, 1200 + 60, 60))

    config, entity_id = await _setup_sensor(
        hass,
        {
            "time_window": {"seconds": time_window},
            "unit_time": UnitOfTime.MINUTES,
            "round": 1,
        }
        | extra_config,
    )

    base = dt_util.utcnow()
    with freeze_time(base) as freezer:
        last_derivative = 0
        for time, value, extra_attributes in zip(
            times, temperature_values, attributes, strict=True
        ):
            now = base + timedelta(seconds=time)
            freezer.move_to(now)
            hass.states.async_set(
                entity_id, value, extra_attributes, force_update=force_update
            )

    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert len(events[1:]) == len(times)
    for time, event in zip(times, events[1:], strict=True):
        state = event.data["new_state"]
        derivative = round(float(state.state), config["sensor"]["round"])

        if time_window == time:
            assert derivative == 1.0
        elif time_window < time < time_window * 2:
            assert (0.1 - 1e-6) < abs(derivative - last_derivative) < (0.1 + 1e-6)
        elif time == time_window * 2:
            assert derivative == 0

        last_derivative = derivative


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
    times = list(range(0, 1800, 30))

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
        for time, value in zip(times, temperature_values, strict=True):
            now = base + timedelta(seconds=time)
            freezer.move_to(now)
            hass.states.async_set(entity_id, value, {})
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
        for time, value in zip(times, temperature_values, strict=True):
            now = base + timedelta(seconds=time)
            freezer.move_to(now)
            hass.states.async_set(entity_id, value, {})
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
        for time, value in zip(times, temperature_values, strict=True):
            now = base + timedelta(seconds=time)
            freezer.move_to(now)
            hass.states.async_set(entity_id, value, {})
            await hass.async_block_till_done()
            state = hass.states.get("sensor.power")
            derivative = round(float(state.state), config["sensor"]["round"])
            if time == times[-1]:
                # Test that the error is never more than
                # (time_window_in_minutes / true_derivative * 100) = 10% + ε
                assert abs(previous - derivative) <= 0.01 + 1e-6
            previous = derivative


async def test_sub_intervals_instantaneous(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    # We simulate the following situation:
    # Value changes from 0 to 10 in 5 seconds (derivative = 2)
    # The max_sub_interval is 20 seconds
    # After max_sub_interval elapses, derivative should change to 0
    # Value changes to 0, 35 seconds after changing to 10 (derivative = -10/35 = -0.29)
    # State goes unavailable, derivative stops changing after that.
    # State goes back to 0, derivative returns to 0 after a max_sub_interval

    max_sub_interval = 20

    config, entity_id = await _setup_sensor(
        hass,
        {
            "unit_time": UnitOfTime.SECONDS,
            "round": 2,
            "max_sub_interval": {"seconds": max_sub_interval},
        },
    )

    base = dt_util.utcnow()
    with freeze_time(base) as freezer:
        freezer.move_to(base)
        hass.states.async_set(entity_id, 0, {}, force_update=True)
        await hass.async_block_till_done()

        now = base + timedelta(seconds=5)
        freezer.move_to(now)
        hass.states.async_set(entity_id, 10, {}, force_update=True)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.power")
        derivative = round(float(state.state), config["sensor"]["round"])
        assert derivative == 2

        # No change yet as sub_interval not elapsed
        now += timedelta(seconds=15)
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.power")
        derivative = round(float(state.state), config["sensor"]["round"])
        assert derivative == 2

        # After 5 more seconds the sub_interval should fire and derivative should be 0
        now += timedelta(seconds=10)
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.power")
        derivative = round(float(state.state), config["sensor"]["round"])
        assert derivative == 0

        now += timedelta(seconds=10)
        freezer.move_to(now)
        hass.states.async_set(entity_id, 0, {}, force_update=True)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.power")
        derivative = round(float(state.state), config["sensor"]["round"])
        assert derivative == -0.29

        now += timedelta(seconds=10)
        freezer.move_to(now)
        hass.states.async_set(entity_id, STATE_UNAVAILABLE, {}, force_update=True)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.power")
        assert state.state == STATE_UNAVAILABLE

        now += timedelta(seconds=60)
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.power")
        assert state.state == STATE_UNAVAILABLE

        now += timedelta(seconds=10)
        freezer.move_to(now)
        hass.states.async_set(entity_id, 0, {}, force_update=True)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.power")
        derivative = round(float(state.state), config["sensor"]["round"])
        assert derivative == 0

        now += timedelta(seconds=max_sub_interval + 1)
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()

        state = hass.states.get("sensor.power")
        derivative = round(float(state.state), config["sensor"]["round"])
        assert derivative == 0


async def test_sub_intervals_with_time_window(hass: HomeAssistant) -> None:
    """Test derivative sensor state."""
    # We simulate the following situation:
    # The value rises by 1 every second for 1 minute, then pauses
    # The time window is 30 seconds
    # The max_sub_interval is 5 seconds
    # After the value stops increasing, the derivative should slowly trend back to 0

    values = []
    for value in range(60):
        values += [value]
    time_window = 30
    max_sub_interval = 5
    times = values

    config, entity_id = await _setup_sensor(
        hass,
        {
            "time_window": {"seconds": time_window},
            "unit_time": UnitOfTime.SECONDS,
            "round": 2,
            "max_sub_interval": {"seconds": max_sub_interval},
        },
    )

    base = dt_util.utcnow()
    with freeze_time(base) as freezer:
        last_state_change = None
        for time, value in zip(times, values, strict=True):
            now = base + timedelta(seconds=time)
            freezer.move_to(now)
            hass.states.async_set(entity_id, value, {}, force_update=True)
            last_state_change = now
            await hass.async_block_till_done()

            if time_window < time:
                state = hass.states.get("sensor.power")
                derivative = round(float(state.state), config["sensor"]["round"])
                # Test that the error is never more than
                # (time_window_in_minutes / true_derivative * 100) = 1% + ε
                assert abs(1 - derivative) <= 0.01 + 1e-6

        for time in range(60):
            now = last_state_change + timedelta(seconds=time)
            freezer.move_to(now)

            async_fire_time_changed(hass, now)
            await hass.async_block_till_done()

            state = hass.states.get("sensor.power")
            derivative = round(float(state.state), config["sensor"]["round"])

            def calc_expected(elapsed_seconds: int, calculation_delay: int = 0):
                last_sub_interval = (
                    elapsed_seconds // max_sub_interval
                ) * max_sub_interval
                return (
                    0
                    if (last_sub_interval >= time_window)
                    else (
                        (time_window - last_sub_interval - calculation_delay)
                        / time_window
                    )
                )

            rounding_err = 0.01 + 1e-6
            expect_max = calc_expected(time) + rounding_err
            # Allow one second of slop for internal delays
            expect_min = calc_expected(time, 1) - rounding_err

            assert expect_min <= derivative <= expect_max, f"Failed at time {time}"


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
        )
        await hass.async_block_till_done()

        freezer.move_to(dt_util.utcnow() + timedelta(seconds=3600))
        hass.states.async_set(
            entity_id,
            2000,
            {"unit_of_measurement": UnitOfPower.WATT},
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.derivative")
    assert state is not None

    # Testing a power sensor increasing by 1000 Watts per hour = 1kW/h
    assert round(float(state.state), config["sensor"]["round"]) == 1.0
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
        hass.states.async_set(entity_id, 1000, {})
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

    _config, entity_id = await _setup_sensor(hass, {"unit_time": UnitOfTime.SECONDS})

    base_time = dt_util.utcnow()
    actual_times = []
    actual_values = []
    with freeze_time(base_time) as freezer:
        for time, value in zip(times, values, strict=True):
            current_time = base_time + timedelta(seconds=time)
            freezer.move_to(current_time)
            hass.states.async_set(
                entity_id,
                value,
                {ATTR_STATE_CLASS: SensorStateClass.TOTAL_INCREASING},
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


@pytest.mark.parametrize("bad_state", [STATE_UNAVAILABLE, STATE_UNKNOWN, "foo"])
async def test_unavailable(
    bad_state: str,
    hass: HomeAssistant,
) -> None:
    """Test derivative sensor state when unavailable."""
    config, entity_id = await _setup_sensor(hass, {"unit_time": "s"})

    times = [0, 1, 2, 3]
    values = [0, 1, bad_state, 2]
    expected_state = [
        0,
        1,
        STATE_UNAVAILABLE if bad_state == STATE_UNAVAILABLE else STATE_UNKNOWN,
        0.5,
    ]

    # Testing a energy sensor with non-monotonic intervals and values
    base = dt_util.utcnow()
    with freeze_time(base) as freezer:
        for time, value, expect in zip(times, values, expected_state, strict=True):
            freezer.move_to(base + timedelta(seconds=time))
            hass.states.async_set(entity_id, value, {})
            await hass.async_block_till_done()

            state = hass.states.get("sensor.power")
            assert state is not None
            rounded_state = (
                state.state
                if expect in [STATE_UNKNOWN, STATE_UNAVAILABLE]
                else round(float(state.state), config["sensor"]["round"])
            )
            assert rounded_state == expect


@pytest.mark.parametrize("bad_state", [STATE_UNAVAILABLE, STATE_UNKNOWN, "foo"])
async def test_unavailable_2(
    bad_state: str,
    hass: HomeAssistant,
) -> None:
    """Test derivative sensor state when unavailable with a time window."""
    config, entity_id = await _setup_sensor(
        hass, {"unit_time": "s", "time_window": {"seconds": 10}}
    )

    # Monotonically increasing by 1, with some unavailable holes
    times = list(range(21))
    values = list(range(21))
    values[3] = bad_state
    values[6] = bad_state
    values[7] = bad_state
    values[8] = bad_state

    base = dt_util.utcnow()
    with freeze_time(base) as freezer:
        for time, value in zip(times, values, strict=True):
            freezer.move_to(base + timedelta(seconds=time))
            hass.states.async_set(entity_id, value, {})
            await hass.async_block_till_done()

            state = hass.states.get("sensor.power")
            assert state is not None

            if value == bad_state:
                assert (
                    state.state == STATE_UNAVAILABLE
                    if bad_state is STATE_UNAVAILABLE
                    else STATE_UNKNOWN
                )
            else:
                expect = (time / 10) if time < 10 else 1
                assert round(float(state.state), config["sensor"]["round"]) == round(
                    expect, config["sensor"]["round"]
                )


@pytest.mark.parametrize("restore_state", ["3.00", STATE_UNKNOWN])
async def test_unavailable_boot(
    restore_state,
    hass: HomeAssistant,
) -> None:
    """Test that the booting sequence does not leave derivative in a bad state."""

    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    "sensor.power",
                    restore_state,
                    {
                        "unit_of_measurement": "kWh/s",
                    },
                ),
                {
                    "native_value": restore_state,
                    "native_unit_of_measurement": "kWh/s",
                },
            ),
        ],
    )

    config = {
        "platform": "derivative",
        "name": "power",
        "source": "sensor.energy",
        "round": 2,
        "unit_time": "s",
    }

    config = {"sensor": config}
    entity_id = config["sensor"]["source"]
    hass.states.async_set(entity_id, STATE_UNAVAILABLE, {})
    await hass.async_block_till_done()

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.power")
    assert state is not None
    # Sensor is unavailable as source is unavailable
    assert state.state == STATE_UNAVAILABLE

    base = dt_util.utcnow()
    with freeze_time(base) as freezer:
        freezer.move_to(base + timedelta(seconds=1))
        hass.states.async_set(entity_id, 10, {"unit_of_measurement": "kWh"})
        await hass.async_block_till_done()

        state = hass.states.get("sensor.power")
        assert state is not None
        # The source sensor has moved to a valid value, but we need 2 points to derive,
        # so just hold until the next tick
        assert state.state == restore_state

        freezer.move_to(base + timedelta(seconds=2))
        hass.states.async_set(entity_id, 15, {"unit_of_measurement": "kWh"})
        await hass.async_block_till_done()

        state = hass.states.get("sensor.power")
        assert state is not None
        # Now that the source sensor has two valid datapoints, we can calculate derivative
        assert state.state == "5.00"
        assert state.attributes.get("unit_of_measurement") == "kWh/s"
