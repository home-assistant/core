"""The tests for the integration sensor platform."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.const import ENERGY_KILO_WATT_HOUR, TIME_SECONDS
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util


async def test_state(hass):
    """Test integration sensor state."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.power",
            "unit": ENERGY_KILO_WATT_HOUR,
            "round": 2,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(entity_id, 1, {})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=3600)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(entity_id, 1, {}, force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None

    # Testing a power sensor at 1 KiloWatts for 1hour = 1kWh
    assert round(float(state.state), config["sensor"]["round"]) == 1.0

    assert state.attributes.get("unit_of_measurement") == ENERGY_KILO_WATT_HOUR


async def test_trapezoidal(hass):
    """Test integration sensor state."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.power",
            "unit": ENERGY_KILO_WATT_HOUR,
            "round": 2,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(entity_id, 0, {})
    await hass.async_block_till_done()

    # Testing a power sensor with non-monotonic intervals and values
    for time, value in [(20, 10), (30, 30), (40, 5), (50, 0)]:
        now = dt_util.utcnow() + timedelta(minutes=time)
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set(entity_id, value, {}, force_update=True)
            await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None

    assert round(float(state.state), config["sensor"]["round"]) == 8.33

    assert state.attributes.get("unit_of_measurement") == ENERGY_KILO_WATT_HOUR


async def test_left(hass):
    """Test integration sensor state with left reimann method."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "method": "left",
            "source": "sensor.power",
            "unit": ENERGY_KILO_WATT_HOUR,
            "round": 2,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(entity_id, 0, {})
    await hass.async_block_till_done()

    # Testing a power sensor with non-monotonic intervals and values
    for time, value in [(20, 10), (30, 30), (40, 5), (50, 0)]:
        now = dt_util.utcnow() + timedelta(minutes=time)
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set(entity_id, value, {}, force_update=True)
            await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None

    assert round(float(state.state), config["sensor"]["round"]) == 7.5

    assert state.attributes.get("unit_of_measurement") == ENERGY_KILO_WATT_HOUR


async def test_right(hass):
    """Test integration sensor state with left reimann method."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "method": "right",
            "source": "sensor.power",
            "unit": ENERGY_KILO_WATT_HOUR,
            "round": 2,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(entity_id, 0, {})
    await hass.async_block_till_done()

    # Testing a power sensor with non-monotonic intervals and values
    for time, value in [(20, 10), (30, 30), (40, 5), (50, 0)]:
        now = dt_util.utcnow() + timedelta(minutes=time)
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set(entity_id, value, {}, force_update=True)
            await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None

    assert round(float(state.state), config["sensor"]["round"]) == 9.17

    assert state.attributes.get("unit_of_measurement") == ENERGY_KILO_WATT_HOUR


async def test_prefix(hass):
    """Test integration sensor state using a power source."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.power",
            "round": 2,
            "unit_prefix": "k",
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(entity_id, 1000, {"unit_of_measurement": "W"})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=3600)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(
            entity_id, 1000, {"unit_of_measurement": "W"}, force_update=True
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None

    # Testing a power sensor at 1000 Watts for 1hour = 1kWh
    assert round(float(state.state), config["sensor"]["round"]) == 1.0
    assert state.attributes.get("unit_of_measurement") == ENERGY_KILO_WATT_HOUR


async def test_suffix(hass):
    """Test integration sensor state using a network counter source."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.bytes_per_second",
            "round": 2,
            "unit_prefix": "k",
            "unit_time": TIME_SECONDS,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(entity_id, 1000, {})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(entity_id, 1000, {}, force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None

    # Testing a network speed sensor at 1000 bytes/s over 10s  = 10kbytes
    assert round(float(state.state)) == 10
