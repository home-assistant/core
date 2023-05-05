"""The tests for the integration sensor platform."""
from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfDataRate,
    UnitOfEnergy,
    UnitOfInformation,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import mock_restore_cache


async def test_state(hass: HomeAssistant) -> None:
    """Test integration sensor state."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.power",
            "round": 2,
        }
    }

    now = dt_util.utcnow()
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        assert await async_setup_component(hass, "sensor", config)

        entity_id = config["sensor"]["source"]
        hass.states.async_set(
            entity_id, 1, {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT}
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None
    assert state.attributes.get("state_class") is SensorStateClass.TOTAL
    assert "device_class" not in state.attributes

    future_now = dt_util.utcnow() + timedelta(seconds=3600)
    with patch("homeassistant.util.dt.utcnow", return_value=future_now):
        hass.states.async_set(
            entity_id,
            1,
            {
                "device_class": SensorDeviceClass.POWER,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT,
            },
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None

    # Testing a power sensor at 1 KiloWatts for 1hour = 1kWh
    assert round(float(state.state), config["sensor"]["round"]) == 1.0

    assert state.attributes.get("unit_of_measurement") == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes.get("device_class") == SensorDeviceClass.ENERGY
    assert state.attributes.get("state_class") is SensorStateClass.TOTAL


async def test_restore_state(hass: HomeAssistant) -> None:
    """Test integration sensor state is restored correctly."""
    mock_restore_cache(
        hass,
        (
            State(
                "sensor.integration",
                "100.0",
                {
                    "device_class": SensorDeviceClass.ENERGY,
                    "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                },
            ),
        ),
    )

    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.power",
            "round": 2,
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state
    assert state.state == "100.00"
    assert state.attributes.get("unit_of_measurement") == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes.get("device_class") == SensorDeviceClass.ENERGY


async def test_restore_state_failed(hass: HomeAssistant) -> None:
    """Test integration sensor state is restored correctly."""
    mock_restore_cache(
        hass,
        (
            State(
                "sensor.integration",
                "INVALID",
                {
                    "last_reset": "2019-10-06T21:00:00.000000",
                },
            ),
        ),
    )

    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.power",
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state
    assert state.state == "unknown"
    assert state.attributes.get("unit_of_measurement") is None
    assert state.attributes.get("state_class") is SensorStateClass.TOTAL

    assert "device_class" not in state.attributes


async def test_trapezoidal(hass: HomeAssistant) -> None:
    """Test integration sensor state."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.power",
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
            hass.states.async_set(
                entity_id,
                value,
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT},
                force_update=True,
            )
            await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None

    assert round(float(state.state), config["sensor"]["round"]) == 8.33

    assert state.attributes.get("unit_of_measurement") == UnitOfEnergy.KILO_WATT_HOUR


async def test_left(hass: HomeAssistant) -> None:
    """Test integration sensor state with left reimann method."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "method": "left",
            "source": "sensor.power",
            "round": 2,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(
        entity_id, 0, {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT}
    )
    await hass.async_block_till_done()

    # Testing a power sensor with non-monotonic intervals and values
    for time, value in [(20, 10), (30, 30), (40, 5), (50, 0)]:
        now = dt_util.utcnow() + timedelta(minutes=time)
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set(
                entity_id,
                value,
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT},
                force_update=True,
            )
            await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None

    assert round(float(state.state), config["sensor"]["round"]) == 7.5

    assert state.attributes.get("unit_of_measurement") == UnitOfEnergy.KILO_WATT_HOUR


async def test_right(hass: HomeAssistant) -> None:
    """Test integration sensor state with left reimann method."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "method": "right",
            "source": "sensor.power",
            "round": 2,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(
        entity_id, 0, {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT}
    )
    await hass.async_block_till_done()

    # Testing a power sensor with non-monotonic intervals and values
    for time, value in [(20, 10), (30, 30), (40, 5), (50, 0)]:
        now = dt_util.utcnow() + timedelta(minutes=time)
        with patch("homeassistant.util.dt.utcnow", return_value=now):
            hass.states.async_set(
                entity_id,
                value,
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT},
                force_update=True,
            )
            await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None

    assert round(float(state.state), config["sensor"]["round"]) == 9.17

    assert state.attributes.get("unit_of_measurement") == UnitOfEnergy.KILO_WATT_HOUR


async def test_prefix(hass: HomeAssistant) -> None:
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
    hass.states.async_set(entity_id, 1000, {"unit_of_measurement": UnitOfPower.WATT})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=3600)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(
            entity_id,
            1000,
            {"unit_of_measurement": UnitOfPower.WATT},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None

    # Testing a power sensor at 1000 Watts for 1hour = 1kWh
    assert round(float(state.state), config["sensor"]["round"]) == 1.0
    assert state.attributes.get("unit_of_measurement") == UnitOfEnergy.KILO_WATT_HOUR


async def test_suffix(hass: HomeAssistant) -> None:
    """Test integration sensor state using a network counter source."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.bytes_per_second",
            "round": 2,
            "unit_prefix": "k",
            "unit_time": UnitOfTime.SECONDS,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(
        entity_id, 1000, {ATTR_UNIT_OF_MEASUREMENT: UnitOfDataRate.BYTES_PER_SECOND}
    )
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(
            entity_id,
            1000,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfDataRate.BYTES_PER_SECOND},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None

    # Testing a network speed sensor at 1000 bytes/s over 10s  = 10kbytes
    assert round(float(state.state)) == 10
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == UnitOfInformation.KILOBYTES


async def test_suffix_2(hass: HomeAssistant) -> None:
    """Test integration sensor state."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.cubic_meters_per_hour",
            "round": 2,
            "unit_time": UnitOfTime.HOURS,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    hass.states.async_set(entity_id, 1000, {ATTR_UNIT_OF_MEASUREMENT: "m³/h"})
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(hours=1)
    with patch("homeassistant.util.dt.utcnow", return_value=now):
        hass.states.async_set(
            entity_id,
            1000,
            {ATTR_UNIT_OF_MEASUREMENT: "m³/h"},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None

    # Testing a flow sensor at 1000 m³/h over 1h = 1000 m³
    assert round(float(state.state)) == 1000
    assert state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "m³"


async def test_units(hass: HomeAssistant) -> None:
    """Test integration sensor units using a power source."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.power",
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    # This replicates the current sequence when HA starts up in a real runtime
    # by updating the base sensor state before the base sensor's units
    # or state have been correctly populated.  Those interim updates
    # include states of None and Unknown
    hass.states.async_set(entity_id, 100, {"unit_of_measurement": None})
    await hass.async_block_till_done()
    hass.states.async_set(entity_id, 200, {"unit_of_measurement": None})
    await hass.async_block_till_done()
    hass.states.async_set(entity_id, 300, {"unit_of_measurement": UnitOfPower.WATT})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None

    # Testing the sensor ignored the source sensor's units until
    # they became valid
    assert state.attributes.get("unit_of_measurement") == UnitOfEnergy.WATT_HOUR

    # When source state goes to None / Unknown, expect an early exit without
    # changes to the state or unit_of_measurement
    hass.states.async_set(entity_id, None, None)
    await hass.async_block_till_done()

    new_state = hass.states.get("sensor.integration")
    assert state == new_state
    assert state.attributes.get("unit_of_measurement") == UnitOfEnergy.WATT_HOUR

    # When source state goes to unavailable, expect sensor to also become unavailable
    hass.states.async_set(entity_id, STATE_UNAVAILABLE, None)
    await hass.async_block_till_done()

    new_state = hass.states.get("sensor.integration")
    assert new_state.state == STATE_UNAVAILABLE


async def test_device_class(hass: HomeAssistant) -> None:
    """Test integration sensor units using a power source."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.power",
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]
    # This replicates the current sequence when HA starts up in a real runtime
    # by updating the base sensor state before the base sensor's units
    # or state have been correctly populated.  Those interim updates
    # include states of None and Unknown
    hass.states.async_set(entity_id, STATE_UNKNOWN, {})
    await hass.async_block_till_done()
    hass.states.async_set(
        entity_id, 100, {"device_class": None, "unit_of_measurement": None}
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        entity_id, 200, {"device_class": None, "unit_of_measurement": None}
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert "device_class" not in state.attributes

    hass.states.async_set(
        entity_id,
        300,
        {
            "device_class": SensorDeviceClass.POWER,
            "unit_of_measurement": UnitOfPower.WATT,
        },
        force_update=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None
    # Testing the sensor ignored the source sensor's device class until
    # it became valid
    assert state.attributes.get("device_class") == SensorDeviceClass.ENERGY


async def test_calc_errors(hass: HomeAssistant) -> None:
    """Test integration sensor units using a power source."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.power",
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]

    hass.states.async_set(entity_id, None, {})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    # With the source sensor in a None state, the Reimann sensor should be
    # unknown
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Moving from an unknown state to a value is a calc error and should
    # not change the value of the Reimann sensor.
    hass.states.async_set(entity_id, 0, {"device_class": None})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # With the source sensor updated successfully, the Reimann sensor
    # should have a zero (known) value.
    hass.states.async_set(entity_id, 1, {"device_class": None})
    await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None
    assert round(float(state.state)) == 0
