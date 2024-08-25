"""The tests for the integration sensor platform."""

from datetime import timedelta
from typing import Any

from freezegun import freeze_time
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.integration.const import DOMAIN
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfDataRate,
    UnitOfEnergy,
    UnitOfInformation,
    UnitOfPower,
    UnitOfTime,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import (
    condition,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

DEFAULT_MAX_SUB_INTERVAL = {"minutes": 1}


@pytest.mark.parametrize(
    ("unit_of_measurement", "device_class", "unit_time"),
    [
        (UnitOfPower.KILO_WATT, SensorDeviceClass.POWER, "h"),
        (UnitOfPower.KILO_WATT, None, "h"),
        (UnitOfPower.BTU_PER_HOUR, SensorDeviceClass.POWER, "h"),
        (
            UnitOfVolumeFlowRate.CUBIC_FEET_PER_MINUTE,
            SensorDeviceClass.VOLUME_FLOW_RATE,
            "min",
        ),
    ],
)
async def test_initial_state(
    hass: HomeAssistant,
    unit_of_measurement: str,
    device_class: SensorDeviceClass,
    unit_time: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test integration sensor state."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.source",
            "round": 2,
            "method": "left",
            "unit_time": unit_time,
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    hass.states.async_set(
        "sensor.source",
        "1",
        {
            ATTR_DEVICE_CLASS: device_class,
            ATTR_UNIT_OF_MEASUREMENT: unit_of_measurement,
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get("sensor.integration") == snapshot


@pytest.mark.parametrize("method", ["trapezoidal", "left", "right"])
async def test_state(hass: HomeAssistant, method) -> None:
    """Test integration sensor state."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.power",
            "round": 2,
            "method": method,
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None
    assert state.attributes.get("state_class") is SensorStateClass.TOTAL
    assert "device_class" not in state.attributes

    now = dt_util.utcnow()
    with freeze_time(now):
        entity_id = config["sensor"]["source"]
        hass.states.async_set(
            entity_id,
            1,
            {
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT,
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None
    assert state.attributes.get("state_class") is SensorStateClass.TOTAL
    assert "device_class" not in state.attributes

    now += timedelta(seconds=3600)
    with freeze_time(now):
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

    # 1 hour after last update, power sensor is unavailable
    now += timedelta(seconds=3600)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            STATE_UNAVAILABLE,
            {
                "device_class": SensorDeviceClass.POWER,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT,
            },
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state.state == STATE_UNAVAILABLE

    # 1 hour after last update, power sensor is back to normal at 2 KiloWatts and stays for 1 hour += 2kWh
    now += timedelta(seconds=3600)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            2,
            {
                "device_class": SensorDeviceClass.POWER,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT,
            },
            force_update=True,
        )
        await hass.async_block_till_done()
    state = hass.states.get("sensor.integration")
    assert (
        round(float(state.state), config["sensor"]["round"]) == 3.0
        if method == "right"
        else 1.0
    )

    now += timedelta(seconds=3600)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            2,
            {
                "device_class": SensorDeviceClass.POWER,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT,
            },
            force_update=True,
        )
        await hass.async_block_till_done()
    state = hass.states.get("sensor.integration")
    assert (
        round(float(state.state), config["sensor"]["round"]) == 5.0
        if method == "right"
        else 3.0
    )


async def test_restore_state(hass: HomeAssistant) -> None:
    """Test integration sensor state is restored correctly."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    "sensor.integration",
                    STATE_UNAVAILABLE,
                    {
                        "device_class": SensorDeviceClass.ENERGY,
                        "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                    },
                ),
                {
                    "native_value": None,
                    "native_unit_of_measurement": "kWh",
                    "source_entity": "sensor.power",
                    "last_valid_state": "100.00",
                },
            ),
        ],
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


@pytest.mark.parametrize(
    "extra_attributes",
    [
        {
            "native_unit_of_measurement": "kWh",
            "source_entity": "sensor.power",
            "last_valid_state": "100.00",
        },
        {
            "native_value": None,
            "native_unit_of_measurement": "kWh",
            "source_entity": "sensor.power",
            "last_valid_state": "None",
        },
    ],
)
async def test_restore_state_failed(hass: HomeAssistant, extra_attributes) -> None:
    """Test integration sensor state is restored correctly."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    "sensor.integration",
                    STATE_UNAVAILABLE,
                    {
                        "device_class": SensorDeviceClass.ENERGY,
                        "unit_of_measurement": UnitOfEnergy.KILO_WATT_HOUR,
                    },
                ),
                extra_attributes,
            ),
        ],
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
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("force_update", [False, True])
@pytest.mark.parametrize(
    "sequence",
    [
        (
            (20, 10, 1.67),
            (30, 30, 5.0),
            (40, 5, 7.92),
            (50, 5, 8.75),
            (60, 0, 9.17),
        ),
    ],
)
async def test_trapezoidal(
    hass: HomeAssistant,
    sequence: tuple[tuple[float, float, float], ...],
    force_update: bool,
) -> None:
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

    start_time = dt_util.utcnow()
    with freeze_time(start_time) as freezer:
        # Testing a power sensor with non-monotonic intervals and values
        for time, value, expected in sequence:
            freezer.move_to(start_time + timedelta(minutes=time))
            hass.states.async_set(
                entity_id,
                value,
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT},
                force_update=force_update,
            )
            await hass.async_block_till_done()
            state = hass.states.get("sensor.integration")
            assert round(float(state.state), config["sensor"]["round"]) == expected

    assert state.attributes.get("unit_of_measurement") == UnitOfEnergy.KILO_WATT_HOUR


@pytest.mark.parametrize("force_update", [False, True])
@pytest.mark.parametrize(
    "sequence",
    [
        (
            (20, 10, 0.0),
            (30, 30, 1.67),
            (40, 5, 6.67),
            (50, 5, 7.5),
            (60, 0, 8.33),
        ),
    ],
)
async def test_left(
    hass: HomeAssistant,
    sequence: tuple[tuple[float, float, float], ...],
    force_update: bool,
) -> None:
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
    start_time = dt_util.utcnow()
    with freeze_time(start_time) as freezer:
        for time, value, expected in sequence:
            freezer.move_to(start_time + timedelta(minutes=time))
            hass.states.async_set(
                entity_id,
                value,
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT},
                force_update=force_update,
            )
            await hass.async_block_till_done()
            state = hass.states.get("sensor.integration")
            assert round(float(state.state), config["sensor"]["round"]) == expected

    assert state.attributes.get("unit_of_measurement") == UnitOfEnergy.KILO_WATT_HOUR


@pytest.mark.parametrize("force_update", [False, True])
@pytest.mark.parametrize(
    "sequence",
    [
        (
            (20, 10, 3.33),
            (30, 30, 8.33),
            (40, 5, 9.17),
            (50, 5, 10.0),
            (60, 0, 10.0),
        ),
    ],
)
async def test_right(
    hass: HomeAssistant,
    sequence: tuple[tuple[float, float, float], ...],
    force_update: bool,
) -> None:
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
    start_time = dt_util.utcnow()
    with freeze_time(start_time) as freezer:
        for time, value, expected in sequence:
            freezer.move_to(start_time + timedelta(minutes=time))
            hass.states.async_set(
                entity_id,
                value,
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT},
                force_update=force_update,
            )
            await hass.async_block_till_done()
            state = hass.states.get("sensor.integration")
            assert round(float(state.state), config["sensor"]["round"]) == expected

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
    with freeze_time(now):
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
    with freeze_time(now):
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
    with freeze_time(now):
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
    hass.states.async_set(entity_id, None, {"unit_of_measurement": UnitOfPower.WATT})
    await hass.async_block_till_done()

    new_state = hass.states.get("sensor.integration")
    assert state == new_state
    assert state.attributes.get("unit_of_measurement") == UnitOfEnergy.WATT_HOUR

    # When source state goes to unavailable, expect sensor to also become unavailable
    hass.states.async_set(entity_id, STATE_UNAVAILABLE, None)
    await hass.async_block_till_done()

    new_state = hass.states.get("sensor.integration")
    assert new_state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("method", ["trapezoidal", "left", "right"])
async def test_device_class(hass: HomeAssistant, method) -> None:
    """Test integration sensor units using a power source."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.power",
            "method": method,
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


@pytest.mark.parametrize(
    ("method", "expected_states"),
    [
        ("trapezoidal", [STATE_UNKNOWN, "0.500", "0.500"]),
        ("left", [STATE_UNKNOWN, "0.000", "1.000"]),
        ("right", ["0.000", "1.000", "1.000"]),
    ],
)
async def test_calc_errors(
    hass: HomeAssistant, method: str, expected_states: list[str]
) -> None:
    """Test integration sensor units using a power source."""
    config = {
        "sensor": {
            "platform": "integration",
            "name": "integration",
            "source": "sensor.power",
            "method": method,
        }
    }

    assert await async_setup_component(hass, "sensor", config)

    entity_id = config["sensor"]["source"]

    now = dt_util.utcnow()
    hass.states.async_set(entity_id, None, {})
    await hass.async_block_till_done()

    # With the source sensor in a None state, the Reimann sensor should be
    # unknown
    state = hass.states.get("sensor.integration")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    # Moving from an unknown state to a value is a calc error and should
    # not change the value of the Reimann sensor, unless the method used is "right".
    now += timedelta(seconds=3600)
    with freeze_time(now):
        hass.states.async_set(entity_id, 0, {"device_class": None})
        await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None
    assert state.state == expected_states[0]

    # With the source sensor updated successfully, the Reimann sensor
    # should have a zero (known) value.
    now += timedelta(seconds=3600)
    with freeze_time(now):
        hass.states.async_set(entity_id, 1, {"device_class": None})
        await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None
    assert state.state == expected_states[1]

    # Set the source sensor back to a non numeric state
    now += timedelta(seconds=3600)
    with freeze_time(now):
        hass.states.async_set(entity_id, "unexpected", {"device_class": None})
        await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.integration")
    assert state is not None
    assert state.state == expected_states[2]


async def test_device_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test for source entity device for Riemann sum integral."""
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

    integration_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "method": "trapezoidal",
            "name": "integration",
            "round": 1.0,
            "source": "sensor.test_source",
            "unit_prefix": "k",
            "unit_time": "min",
        },
        title="Integration",
    )

    integration_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(integration_config_entry.entry_id)
    await hass.async_block_till_done()

    integration_entity = entity_registry.async_get("sensor.integration")
    assert integration_entity is not None
    assert integration_entity.device_id == source_entity.device_id


def _integral_sensor_config(max_sub_interval: dict[str, int] | None) -> dict[str, Any]:
    sensor = {
        "platform": "integration",
        "name": "integration",
        "source": "sensor.power",
        "method": "right",
    }
    if max_sub_interval is not None:
        sensor["max_sub_interval"] = max_sub_interval
    return {"sensor": sensor}


async def _setup_integral_sensor(
    hass: HomeAssistant, max_sub_interval: dict[str, int] | None
) -> None:
    await async_setup_component(
        hass, "sensor", _integral_sensor_config(max_sub_interval=max_sub_interval)
    )
    await hass.async_block_till_done()


async def _update_source_sensor(hass: HomeAssistant, value: int | str) -> None:
    hass.states.async_set(
        _integral_sensor_config(max_sub_interval=DEFAULT_MAX_SUB_INTERVAL)["sensor"][
            "source"
        ],
        value,
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfPower.KILO_WATT},
        force_update=True,
    )
    await hass.async_block_till_done()


async def test_on_valid_source_expect_update_on_time(
    hass: HomeAssistant,
) -> None:
    """Test whether time based integration updates the integral on a valid source."""
    start_time = dt_util.utcnow()

    with freeze_time(start_time) as freezer:
        await _setup_integral_sensor(hass, max_sub_interval=DEFAULT_MAX_SUB_INTERVAL)
        await _update_source_sensor(hass, 100)
        state_before_max_sub_interval_exceeded = hass.states.get("sensor.integration")

        freezer.tick(61)
        async_fire_time_changed(hass, dt_util.now())
        await hass.async_block_till_done()

        state = hass.states.get("sensor.integration")
        assert (
            condition.async_numeric_state(hass, state_before_max_sub_interval_exceeded)
            is False
        )
        assert state_before_max_sub_interval_exceeded.state != state.state
        assert condition.async_numeric_state(hass, state) is True
        assert float(state.state) > 1.69  # approximately 100 * 61 / 3600
        assert float(state.state) < 1.8


async def test_on_unvailable_source_expect_no_update_on_time(
    hass: HomeAssistant,
) -> None:
    """Test whether time based integration handles unavailability of the source properly."""

    start_time = dt_util.utcnow()
    with freeze_time(start_time) as freezer:
        await _setup_integral_sensor(hass, max_sub_interval=DEFAULT_MAX_SUB_INTERVAL)
        await _update_source_sensor(hass, 100)
        freezer.tick(61)
        async_fire_time_changed(hass, dt_util.now())
        await hass.async_block_till_done()

        state = hass.states.get("sensor.integration")
        assert condition.async_numeric_state(hass, state) is True

        await _update_source_sensor(hass, STATE_UNAVAILABLE)
        await hass.async_block_till_done()

        freezer.tick(61)
        async_fire_time_changed(hass, dt_util.now())
        await hass.async_block_till_done()

        state = hass.states.get("sensor.integration")
        assert condition.state(hass, state, STATE_UNAVAILABLE) is True


async def test_on_statechanges_source_expect_no_update_on_time(
    hass: HomeAssistant,
) -> None:
    """Test whether state changes cancel time based integration."""

    start_time = dt_util.utcnow()
    with freeze_time(start_time) as freezer:
        await _setup_integral_sensor(hass, max_sub_interval=DEFAULT_MAX_SUB_INTERVAL)
        await _update_source_sensor(hass, 100)

        freezer.tick(30)
        await hass.async_block_till_done()
        await _update_source_sensor(hass, 101)

        state_after_30s = hass.states.get("sensor.integration")
        assert condition.async_numeric_state(hass, state_after_30s) is True

        freezer.tick(35)
        async_fire_time_changed(hass, dt_util.now())
        await hass.async_block_till_done()
        state_after_65s = hass.states.get("sensor.integration")
        assert (dt_util.now() - start_time).total_seconds() > 60
        # No state change because the timer was cancelled because of an update after 30s
        assert state_after_65s == state_after_30s

        freezer.tick(35)
        async_fire_time_changed(hass, dt_util.now())
        await hass.async_block_till_done()
        state_after_105s = hass.states.get("sensor.integration")
        # Update based on time
        assert float(state_after_105s.state) > float(state_after_65s.state)


async def test_on_no_max_sub_interval_expect_no_timebased_updates(
    hass: HomeAssistant,
) -> None:
    """Test whether integratal is not updated by time when max_sub_interval is not configured."""

    start_time = dt_util.utcnow()
    with freeze_time(start_time) as freezer:
        await _setup_integral_sensor(hass, max_sub_interval=None)
        await _update_source_sensor(hass, 100)
        await hass.async_block_till_done()
        await _update_source_sensor(hass, 101)
        await hass.async_block_till_done()

        state_after_last_state_change = hass.states.get("sensor.integration")

        assert (
            condition.async_numeric_state(hass, state_after_last_state_change) is True
        )

        freezer.tick(100)
        async_fire_time_changed(hass, dt_util.now())
        await hass.async_block_till_done()
        state_after_100s = hass.states.get("sensor.integration")
        assert state_after_100s == state_after_last_state_change
