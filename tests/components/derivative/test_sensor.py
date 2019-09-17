"""The tests for the derivative sensor platform."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util


async def test_state(hass):
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
    hass.states.async_set(entity_id, 1, {})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=3600)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(entity_id, 1, {}, force_update=True)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.derivative")
    assert state is not None

    # Testing a energy sensor at 1 kWh for 1hour = 0kW
    assert round(float(state.state), config["sensor"]["round"]) == 0.0

    assert state.attributes.get("unit_of_measurement") == "kW"


async def test_dataSet1(hass):
    """Test derivative sensor state."""
    config = {
        "sensor": {
            "platform": "derivative",
            "name": "power",
            "source": "sensor.energy",
            "unit_time": "s",
            "round": 2,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(entity_id, 0, {})
    await hass.async_block_till_done()

    # Testing a energy sensor with non-monotonic intervals and values
    for time, value in [(20, 10), (30, 30), (40, 5), (50, 0)]:
        now = dt_util.utcnow() + timedelta(seconds=time)
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set(entity_id, value, {}, force_update=True)
            await hass.async_block_till_done()

    state = hass.states.get("sensor.power")
    assert state is not None

    assert round(float(state.state), config["sensor"]["round"]) == -0.5


async def test_dataSet2(hass):
    """Test derivative sensor state."""
    config = {
        "sensor": {
            "platform": "derivative",
            "name": "power",
            "source": "sensor.energy",
            "unit_time": "s",
            "round": 2,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(entity_id, 0, {})
    await hass.async_block_till_done()

    # Testing a energy sensor with non-monotonic intervals and values
    for time, value in [(20, 5), (30, 0)]:
        now = dt_util.utcnow() + timedelta(seconds=time)
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set(entity_id, value, {}, force_update=True)
            await hass.async_block_till_done()

    state = hass.states.get("sensor.power")
    assert state is not None

    assert round(float(state.state), config["sensor"]["round"]) == -0.5


async def test_dataSet3(hass):
    """Test derivative sensor state."""
    config = {
        "sensor": {
            "platform": "derivative",
            "name": "power",
            "source": "sensor.energy",
            "unit_time": "s",
            "round": 2,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(entity_id, 0, {})
    await hass.async_block_till_done()

    # Testing a energy sensor with non-monotonic intervals and values
    for time, value in [(20, 5), (30, 10)]:
        now = dt_util.utcnow() + timedelta(seconds=time)
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set(entity_id, value, {}, force_update=True)
            await hass.async_block_till_done()

    state = hass.states.get("sensor.power")
    assert state is not None

    assert round(float(state.state), config["sensor"]["round"]) == 0.5

    assert state.attributes.get("unit_of_measurement") == "/s"


async def test_dataSet4(hass):
    """Test derivative sensor state."""
    config = {
        "sensor": {
            "platform": "derivative",
            "name": "power",
            "source": "sensor.energy",
            "unit_time": "s",
            "round": 2,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(entity_id, 0, {})
    await hass.async_block_till_done()

    # Testing a energy sensor with non-monotonic intervals and values
    for time, value in [(20, 5), (30, 5)]:
        now = dt_util.utcnow() + timedelta(seconds=time)
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set(entity_id, value, {}, force_update=True)
            await hass.async_block_till_done()

    state = hass.states.get("sensor.power")
    assert state is not None

    assert round(float(state.state), config["sensor"]["round"]) == 0


async def test_dataSet5(hass):
    """Test derivative sensor state."""
    config = {
        "sensor": {
            "platform": "derivative",
            "name": "power",
            "source": "sensor.energy",
            "unit_time": "s",
            "round": 2,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(entity_id, 0, {})
    await hass.async_block_till_done()

    # Testing a energy sensor with non-monotonic intervals and values
    for time, value in [(20, 10), (30, -10)]:
        now = dt_util.utcnow() + timedelta(seconds=time)
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set(entity_id, value, {}, force_update=True)
            await hass.async_block_till_done()

    state = hass.states.get("sensor.power")
    assert state is not None

    assert round(float(state.state), config["sensor"]["round"]) == -2


async def test_dataSet6(hass):
    """Test derivative sensor state."""
    config = {
        "sensor": {
            "platform": "derivative",
            "name": "power",
            "source": "sensor.energy",
            "round": 2,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(entity_id, 0, {})
    await hass.async_block_till_done()

    # Testing a energy sensor with non-monotonic intervals and values
    for time, value in [(20, 0), (30, 36000)]:
        now = dt_util.utcnow() + timedelta(seconds=time)
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set(entity_id, value, {}, force_update=True)
            await hass.async_block_till_done()

    state = hass.states.get("sensor.power")
    assert state is not None

    assert round(float(state.state), config["sensor"]["round"]) == 1


async def test_prefix(hass):
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
    hass.states.async_set(
        entity_id, 1000, {"unit_of_measurement": "W"}, force_update=True
    )
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=3600)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(
            entity_id, 1000, {"unit_of_measurement": "W"}, force_update=True
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.derivative")
    assert state is not None

    # Testing a power sensor at 1000 Watts for 1hour = 0kW/h
    assert round(float(state.state), config["sensor"]["round"]) == 0.0
    assert state.attributes.get("unit_of_measurement") == "kW/h"


async def test_suffix(hass):
    """Test derivative sensor state using a network counter source."""
    config = {
        "sensor": {
            "platform": "derivative",
            "name": "derivative",
            "source": "sensor.bytes_per_second",
            "round": 2,
            "unit_prefix": "k",
            "unit_time": "s",
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

    state = hass.states.get("sensor.derivative")
    assert state is not None

    # Testing a network speed sensor at 1000 bytes/s over 10s  = 10kbytes/s2
    assert round(float(state.state), config["sensor"]["round"]) == 0.0
