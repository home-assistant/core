"""The tests for the utility_meter sensor platform."""

from datetime import timedelta

from freezegun import freeze_time
import pytest

from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.components.utility_meter import DEFAULT_OFFSET
from homeassistant.components.utility_meter.const import (
    ATTR_VALUE,
    DAILY,
    DOMAIN,
    HOURLY,
    QUARTER_HOURLY,
    SERVICE_CALIBRATE_METER,
    SERVICE_RESET,
)
from homeassistant.components.utility_meter.sensor import (
    ATTR_LAST_RESET,
    ATTR_LAST_VALID_STATE,
    ATTR_STATUS,
    COLLECTING,
    PAUSED,
    UtilityMeterSensor,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_UNIT_OF_MEASUREMENT,
    EVENT_HOMEASSISTANT_STARTED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfVolume,
)
from homeassistant.core import CoreState, HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)


@pytest.fixture(autouse=True)
def set_utc(hass: HomeAssistant):
    """Set timezone to UTC."""
    hass.config.set_time_zone("UTC")


@pytest.mark.parametrize(
    ("yaml_config", "config_entry_config"),
    [
        (
            {
                "utility_meter": {
                    "energy_bill": {
                        "source": "sensor.energy",
                        "tariffs": ["onpeak", "midpeak", "offpeak"],
                    }
                }
            },
            None,
        ),
        (
            None,
            {
                "cycle": "none",
                "delta_values": False,
                "name": "Energy bill",
                "net_consumption": False,
                "offset": 0,
                "periodically_resetting": True,
                "source": "sensor.energy",
                "tariffs": ["onpeak", "midpeak", "offpeak"],
            },
        ),
    ],
)
async def test_state(hass: HomeAssistant, yaml_config, config_entry_config) -> None:
    """Test utility sensor state."""
    if yaml_config:
        assert await async_setup_component(hass, DOMAIN, yaml_config)
        await hass.async_block_till_done()
        entity_id = yaml_config[DOMAIN]["energy_bill"]["source"]
    else:
        config_entry = MockConfigEntry(
            data={},
            domain=DOMAIN,
            options=config_entry_config,
            title=config_entry_config["name"],
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        entity_id = config_entry_config["source"]

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    hass.states.async_set(
        entity_id, 2, {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR}
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_onpeak")
    assert state is not None
    assert state.state == "0"
    assert state.attributes.get("status") == COLLECTING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR

    state = hass.states.get("sensor.energy_bill_midpeak")
    assert state is not None
    assert state.state == "0"
    assert state.attributes.get("status") == PAUSED
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state is not None
    assert state.state == "0"
    assert state.attributes.get("status") == PAUSED
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR

    now = dt_util.utcnow() + timedelta(seconds=10)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            3,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_onpeak")
    assert state is not None
    assert state.state == "1"
    assert state.attributes.get("status") == COLLECTING

    state = hass.states.get("sensor.energy_bill_midpeak")
    assert state is not None
    assert state.state == "0"
    assert state.attributes.get("status") == PAUSED

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state is not None
    assert state.state == "0"
    assert state.attributes.get("status") == PAUSED

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.energy_bill", "option": "offpeak"},
        blocking=True,
    )

    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=20)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            6,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_onpeak")
    assert state is not None
    assert state.state == "1"
    assert state.attributes.get("status") == PAUSED

    state = hass.states.get("sensor.energy_bill_midpeak")
    assert state is not None
    assert state.state == "0"
    assert state.attributes.get("status") == PAUSED

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state is not None
    assert state.state == "3"
    assert state.attributes.get("status") == COLLECTING

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CALIBRATE_METER,
        {ATTR_ENTITY_ID: "sensor.energy_bill_midpeak", ATTR_VALUE: "100"},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_bill_midpeak")
    assert state is not None
    assert state.state == "100"

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CALIBRATE_METER,
        {ATTR_ENTITY_ID: "sensor.energy_bill_midpeak", ATTR_VALUE: "0.123"},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_bill_midpeak")
    assert state is not None
    assert state.state == "0.123"

    # test invalid state
    hass.states.async_set(
        entity_id, "*", {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR}
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state is not None
    assert state.state == "3"

    # test unavailable source
    hass.states.async_set(
        entity_id,
        STATE_UNAVAILABLE,
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state is not None
    assert state.state == "unavailable"


@pytest.mark.parametrize(
    ("yaml_config", "config_entry_config"),
    [
        (
            {
                "utility_meter": {
                    "energy_bill": {
                        "source": "sensor.energy",
                        "always_available": True,
                    }
                }
            },
            None,
        ),
        (
            None,
            {
                "cycle": "none",
                "delta_values": False,
                "name": "Energy bill",
                "net_consumption": False,
                "offset": 0,
                "periodically_resetting": True,
                "source": "sensor.energy",
                "tariffs": [],
                "always_available": True,
            },
        ),
    ],
)
async def test_state_always_available(
    hass: HomeAssistant, yaml_config, config_entry_config
) -> None:
    """Test utility sensor state."""
    if yaml_config:
        assert await async_setup_component(hass, DOMAIN, yaml_config)
        await hass.async_block_till_done()
        entity_id = yaml_config[DOMAIN]["energy_bill"]["source"]
    else:
        config_entry = MockConfigEntry(
            data={},
            domain=DOMAIN,
            options=config_entry_config,
            title=config_entry_config["name"],
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        entity_id = config_entry_config["source"]

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    hass.states.async_set(
        entity_id, 2, {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR}
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    assert state is not None
    assert state.state == "0"
    assert state.attributes.get("status") == COLLECTING
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR

    now = dt_util.utcnow() + timedelta(seconds=10)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            3,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    assert state is not None
    assert state.state == "1"
    assert state.attributes.get("status") == COLLECTING

    # test unavailable state
    hass.states.async_set(
        entity_id,
        "unavailable",
        {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_bill")
    assert state is not None
    assert state.state == "1"

    # test unknown state
    hass.states.async_set(
        entity_id, None, {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR}
    )
    await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_bill")
    assert state is not None
    assert state.state == "1"


@pytest.mark.parametrize(
    "yaml_config",
    [
        (
            {
                "utility_meter": {
                    "energy_bill": {
                        "source": "sensor.energy",
                        "tariffs": ["onpeak", "onpeak"],
                    }
                }
            },
            None,
        ),
    ],
)
async def test_not_unique_tariffs(hass: HomeAssistant, yaml_config) -> None:
    """Test utility sensor state initializtion."""
    assert not await async_setup_component(hass, DOMAIN, yaml_config)


@pytest.mark.parametrize(
    ("yaml_config", "config_entry_config"),
    [
        (
            {
                "utility_meter": {
                    "energy_bill": {
                        "source": "sensor.energy",
                        "tariffs": ["onpeak", "midpeak", "offpeak"],
                    }
                }
            },
            None,
        ),
        (
            None,
            {
                "cycle": "none",
                "delta_values": False,
                "name": "Energy bill",
                "net_consumption": False,
                "offset": 0,
                "periodically_resetting": True,
                "source": "sensor.energy",
                "tariffs": ["onpeak", "midpeak", "offpeak"],
            },
        ),
    ],
)
async def test_init(hass: HomeAssistant, yaml_config, config_entry_config) -> None:
    """Test utility sensor state initializtion."""
    if yaml_config:
        assert await async_setup_component(hass, DOMAIN, yaml_config)
        await hass.async_block_till_done()
        entity_id = yaml_config[DOMAIN]["energy_bill"]["source"]
    else:
        config_entry = MockConfigEntry(
            data={},
            domain=DOMAIN,
            options=config_entry_config,
            title=config_entry_config["name"],
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        entity_id = config_entry_config["source"]

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_onpeak")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    hass.states.async_set(
        entity_id, 2, {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR}
    )

    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_onpeak")
    assert state is not None
    assert state.state == "0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR

    state = hass.states.get("sensor.energy_bill_offpeak")
    assert state is not None
    assert state.state == "0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR


async def test_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test unique_id configuration option."""
    yaml_config = {
        "utility_meter": {
            "energy_bill": {
                "name": "Provider A",
                "unique_id": "1",
                "source": "sensor.energy",
                "tariffs": ["onpeak", "midpeak", "offpeak"],
            }
        }
    }
    assert await async_setup_component(hass, DOMAIN, yaml_config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert len(entity_registry.entities) == 4
    assert entity_registry.entities["select.energy_bill"].unique_id == "1"
    assert entity_registry.entities["sensor.energy_bill_onpeak"].unique_id == "1_onpeak"


@pytest.mark.parametrize(
    ("yaml_config", "entity_id", "name"),
    [
        (
            {
                "utility_meter": {
                    "energy_bill": {
                        "name": "dog",
                        "source": "sensor.energy",
                        "tariffs": ["onpeak", "midpeak", "offpeak"],
                    }
                }
            },
            "sensor.energy_bill_onpeak",
            "dog onpeak",
        ),
        (
            {
                "utility_meter": {
                    "energy_bill": {
                        "name": "dog",
                        "source": "sensor.energy",
                    }
                }
            },
            "sensor.dog",
            "dog",
        ),
        (
            {
                "utility_meter": {
                    "energy_bill": {
                        "source": "sensor.energy",
                    }
                }
            },
            "sensor.energy_bill",
            "energy_bill",
        ),
    ],
)
async def test_entity_name(hass: HomeAssistant, yaml_config, entity_id, name) -> None:
    """Test utility sensor state initializtion."""
    assert await async_setup_component(hass, DOMAIN, yaml_config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.name == name


@pytest.mark.parametrize(
    ("yaml_config", "config_entry_configs"),
    [
        (
            {
                "utility_meter": {
                    "energy_meter": {
                        "source": "sensor.energy",
                        "net_consumption": True,
                    },
                    "gas_meter": {
                        "source": "sensor.gas",
                    },
                }
            },
            None,
        ),
        (
            None,
            [
                {
                    "cycle": "none",
                    "delta_values": False,
                    "name": "Energy meter",
                    "net_consumption": True,
                    "offset": 0,
                    "periodically_resetting": True,
                    "source": "sensor.energy",
                    "tariffs": [],
                },
                {
                    "cycle": "none",
                    "delta_values": False,
                    "name": "Gas meter",
                    "net_consumption": False,
                    "offset": 0,
                    "periodically_resetting": True,
                    "source": "sensor.gas",
                    "tariffs": [],
                },
            ],
        ),
    ],
)
@pytest.mark.parametrize(
    (
        "energy_sensor_attributes",
        "gas_sensor_attributes",
        "energy_meter_attributes",
        "gas_meter_attributes",
    ),
    [
        (
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            {ATTR_UNIT_OF_MEASUREMENT: "some_archaic_unit"},
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.ENERGY,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
            },
            {
                ATTR_DEVICE_CLASS: None,
                ATTR_UNIT_OF_MEASUREMENT: "some_archaic_unit",
            },
        ),
        (
            {},
            {},
            {
                ATTR_DEVICE_CLASS: None,
                ATTR_UNIT_OF_MEASUREMENT: None,
            },
            {
                ATTR_DEVICE_CLASS: None,
                ATTR_UNIT_OF_MEASUREMENT: None,
            },
        ),
        (
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.GAS,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
            },
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.WATER,
                ATTR_UNIT_OF_MEASUREMENT: "some_archaic_unit",
            },
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.GAS,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR,
            },
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.WATER,
                ATTR_UNIT_OF_MEASUREMENT: "some_archaic_unit",
            },
        ),
    ],
)
async def test_device_class(
    hass: HomeAssistant,
    yaml_config,
    config_entry_configs,
    energy_sensor_attributes,
    gas_sensor_attributes,
    energy_meter_attributes,
    gas_meter_attributes,
) -> None:
    """Test utility device_class."""
    if yaml_config:
        assert await async_setup_component(hass, DOMAIN, yaml_config)
        await hass.async_block_till_done()
    else:
        for config_entry_config in config_entry_configs:
            config_entry = MockConfigEntry(
                data={},
                domain=DOMAIN,
                options=config_entry_config,
                title=config_entry_config["name"],
            )
            config_entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

    entity_id_energy = "sensor.energy"
    entity_id_gas = "sensor.gas"

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)

    await hass.async_block_till_done()

    hass.states.async_set(entity_id_energy, 2, energy_sensor_attributes)
    hass.states.async_set(entity_id_gas, 2, gas_sensor_attributes)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_meter")
    assert state is not None
    assert state.state == "0"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL
    for attr, value in energy_meter_attributes.items():
        assert state.attributes.get(attr) == value

    state = hass.states.get("sensor.gas_meter")
    assert state is not None
    assert state.state == "0"
    assert state.attributes.get(ATTR_STATE_CLASS) is SensorStateClass.TOTAL_INCREASING
    for attr, value in gas_meter_attributes.items():
        assert state.attributes.get(attr) == value


@pytest.mark.parametrize(
    ("yaml_config", "config_entry_config"),
    [
        (
            {
                "utility_meter": {
                    "energy_bill": {
                        "source": "sensor.energy",
                        "tariffs": [
                            "tariff0",
                            "tariff1",
                            "tariff2",
                            "tariff3",
                            "tariff4",
                        ],
                    }
                }
            },
            None,
        ),
        (
            None,
            {
                "cycle": "none",
                "delta_values": False,
                "name": "Energy bill",
                "net_consumption": False,
                "offset": 0,
                "periodically_resetting": True,
                "source": "sensor.energy",
                "tariffs": [
                    "tariff0",
                    "tariff1",
                    "tariff2",
                    "tariff3",
                    "tariff4",
                ],
            },
        ),
    ],
)
async def test_restore_state(
    hass: HomeAssistant, yaml_config, config_entry_config
) -> None:
    """Test utility sensor restore state."""
    # Home assistant is not runnit yet
    hass.set_state(CoreState.not_running)

    last_reset_1 = "2020-12-21T00:00:00.013073+00:00"
    last_reset_2 = "2020-12-22T00:00:00.013073+00:00"

    mock_restore_cache_with_extra_data(
        hass,
        [
            # sensor.energy_bill_tariff0 is restored as expected, including device
            # class
            (
                State(
                    "sensor.energy_bill_tariff0",
                    "0.1",
                    attributes={
                        ATTR_STATUS: PAUSED,
                        ATTR_LAST_RESET: last_reset_1,
                        ATTR_UNIT_OF_MEASUREMENT: UnitOfVolume.CUBIC_METERS,
                    },
                ),
                {
                    "native_value": {
                        "__type": "<class 'decimal.Decimal'>",
                        "decimal_str": "0.2",
                    },
                    "native_unit_of_measurement": "gal",
                    "last_reset": last_reset_2,
                    "last_period": "1.3",
                    "last_valid_state": None,
                    "status": "collecting",
                    "input_device_class": "water",
                },
            ),
            # sensor.energy_bill_tariff1 is restored as expected, except device
            # class
            (
                State(
                    "sensor.energy_bill_tariff1",
                    "1.1",
                    attributes={
                        ATTR_STATUS: PAUSED,
                        ATTR_LAST_RESET: last_reset_1,
                        ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.MEGA_WATT_HOUR,
                    },
                ),
                {
                    "native_value": {
                        "__type": "<class 'decimal.Decimal'>",
                        "decimal_str": "1.2",
                    },
                    "native_unit_of_measurement": "kWh",
                    "last_reset": last_reset_2,
                    "last_period": "1.3",
                    "last_valid_state": None,
                    "status": "paused",
                },
            ),
            # sensor.energy_bill_tariff2 has missing keys and falls back to
            # saved state
            (
                State(
                    "sensor.energy_bill_tariff2",
                    "2.1",
                    attributes={
                        ATTR_STATUS: PAUSED,
                        ATTR_LAST_RESET: last_reset_1,
                        ATTR_LAST_VALID_STATE: None,
                        ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.MEGA_WATT_HOUR,
                    },
                ),
                {
                    "native_value": {
                        "__type": "<class 'decimal.Decimal'>",
                        "decimal_str": "2.2",
                    },
                    "native_unit_of_measurement": "kWh",
                    "last_valid_state": "None",
                },
            ),
            # sensor.energy_bill_tariff3 has invalid data and falls back to
            # saved state
            (
                State(
                    "sensor.energy_bill_tariff3",
                    "3.1",
                    attributes={
                        ATTR_STATUS: COLLECTING,
                        ATTR_LAST_RESET: last_reset_1,
                        ATTR_LAST_VALID_STATE: None,
                        ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.MEGA_WATT_HOUR,
                    },
                ),
                {
                    "native_value": {
                        "__type": "<class 'decimal.Decimal'>",
                        "decimal_str": "3f",  # Invalid
                    },
                    "native_unit_of_measurement": "kWh",
                    "last_valid_state": "None",
                },
            ),
            # No extra saved data, fall back to saved state
            (
                State(
                    "sensor.energy_bill_tariff4",
                    "error",
                    attributes={
                        ATTR_STATUS: COLLECTING,
                        ATTR_LAST_RESET: last_reset_1,
                        ATTR_LAST_VALID_STATE: None,
                        ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.MEGA_WATT_HOUR,
                    },
                ),
                {},
            ),
        ],
    )

    if yaml_config:
        assert await async_setup_component(hass, DOMAIN, yaml_config)
        await hass.async_block_till_done()
    else:
        config_entry = MockConfigEntry(
            data={},
            domain=DOMAIN,
            options=config_entry_config,
            title=config_entry_config["name"],
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # restore from cache
    state = hass.states.get("sensor.energy_bill_tariff0")
    assert state.state == "0.2"
    assert state.attributes.get("status") == COLLECTING
    assert state.attributes.get("last_reset") == last_reset_2
    assert state.attributes.get("last_valid_state") == "None"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfVolume.GALLONS
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.WATER

    state = hass.states.get("sensor.energy_bill_tariff1")
    assert state.state == "1.2"
    assert state.attributes.get("status") == PAUSED
    assert state.attributes.get("last_reset") == last_reset_2
    assert state.attributes.get("last_valid_state") == "None"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY

    state = hass.states.get("sensor.energy_bill_tariff2")
    assert state.state == "2.1"
    assert state.attributes.get("status") == PAUSED
    assert state.attributes.get("last_reset") == last_reset_1
    assert state.attributes.get("last_valid_state") == "None"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.MEGA_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY

    state = hass.states.get("sensor.energy_bill_tariff3")
    assert state.state == "3.1"
    assert state.attributes.get("status") == COLLECTING
    assert state.attributes.get("last_reset") == last_reset_1
    assert state.attributes.get("last_valid_state") == "None"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.MEGA_WATT_HOUR
    assert state.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY

    state = hass.states.get("sensor.energy_bill_tariff4")
    assert state.state == STATE_UNKNOWN

    # utility_meter is loaded, now set sensors according to utility_meter:

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    state = hass.states.get("select.energy_bill")
    assert state.state == "tariff0"

    state = hass.states.get("sensor.energy_bill_tariff0")
    assert state.attributes.get("status") == COLLECTING

    for entity_id in (
        "sensor.energy_bill_tariff1",
        "sensor.energy_bill_tariff2",
        "sensor.energy_bill_tariff3",
        "sensor.energy_bill_tariff4",
    ):
        state = hass.states.get(entity_id)
        assert state.attributes.get("status") == PAUSED


@pytest.mark.parametrize(
    ("yaml_config", "config_entry_config"),
    [
        (
            {
                "utility_meter": {
                    "energy_bill": {
                        "source": "sensor.energy",
                    }
                }
            },
            None,
        ),
        (
            None,
            {
                "cycle": "none",
                "delta_values": False,
                "name": "Energy bill",
                "net_consumption": False,
                "offset": 0,
                "periodically_resetting": True,
                "source": "sensor.energy",
                "tariffs": [],
            },
        ),
    ],
)
async def test_service_reset_no_tariffs(
    hass: HomeAssistant, yaml_config, config_entry_config
) -> None:
    """Test utility sensor service reset for sensor with no tariffs."""
    # Home assistant is not runnit yet
    hass.state = CoreState.not_running
    last_reset = "2023-10-01T00:00:00+00:00"

    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    "sensor.energy_bill",
                    "3",
                    attributes={
                        ATTR_LAST_RESET: last_reset,
                    },
                ),
                {},
            ),
        ],
    )

    if yaml_config:
        assert await async_setup_component(hass, DOMAIN, yaml_config)
        await hass.async_block_till_done()
    else:
        config_entry = MockConfigEntry(
            data={},
            domain=DOMAIN,
            options=config_entry_config,
            title=config_entry_config["name"],
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    assert state
    assert state.state == "3"
    assert state.attributes.get("last_reset") == last_reset
    assert state.attributes.get("last_period") == "0"

    now = dt_util.utcnow()
    with freeze_time(now):
        await hass.services.async_call(
            domain=DOMAIN,
            service=SERVICE_RESET,
            service_data={},
            target={"entity_id": "sensor.energy_bill"},
            blocking=True,
        )

        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    assert state
    assert state.state == "0"
    assert state.attributes.get("last_reset") == now.isoformat()
    assert state.attributes.get("last_period") == "3"


@pytest.mark.parametrize(
    ("yaml_config", "config_entry_configs"),
    [
        (
            {
                "utility_meter": {
                    "energy_bill": {
                        "source": "sensor.energy",
                    },
                    "water_bill": {
                        "source": "sensor.water",
                    },
                },
            },
            None,
        ),
        (
            None,
            [
                {
                    "cycle": "none",
                    "delta_values": False,
                    "name": "Energy bill",
                    "net_consumption": False,
                    "offset": 0,
                    "periodically_resetting": True,
                    "source": "sensor.energy",
                    "tariffs": [],
                },
                {
                    "cycle": "none",
                    "delta_values": False,
                    "name": "Water bill",
                    "net_consumption": False,
                    "offset": 0,
                    "periodically_resetting": True,
                    "source": "sensor.water",
                    "tariffs": [],
                },
            ],
        ),
    ],
)
async def test_service_reset_no_tariffs_correct_with_multi(
    hass: HomeAssistant, yaml_config, config_entry_configs
) -> None:
    """Test complex utility sensor service reset for multiple sensors with no tarrifs.

    See GitHub issue #114864: Service "utility_meter.reset" affects all meters.
    """

    # Home assistant is not runnit yet
    hass.state = CoreState.not_running
    last_reset = "2023-10-01T00:00:00+00:00"

    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    "sensor.energy_bill",
                    "3",
                    attributes={
                        ATTR_LAST_RESET: last_reset,
                    },
                ),
                {},
            ),
            (
                State(
                    "sensor.water_bill",
                    "6",
                    attributes={
                        ATTR_LAST_RESET: last_reset,
                    },
                ),
                {},
            ),
        ],
    )

    if yaml_config:
        assert await async_setup_component(hass, DOMAIN, yaml_config)
        await hass.async_block_till_done()
    else:
        for entry in config_entry_configs:
            config_entry = MockConfigEntry(
                data={},
                domain=DOMAIN,
                options=entry,
                title=entry["name"],
            )
            config_entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    assert state
    assert state.state == "3"
    assert state.attributes.get("last_reset") == last_reset
    assert state.attributes.get("last_period") == "0"

    state = hass.states.get("sensor.water_bill")
    assert state
    assert state.state == "6"
    assert state.attributes.get("last_reset") == last_reset
    assert state.attributes.get("last_period") == "0"

    now = dt_util.utcnow()
    with freeze_time(now):
        await hass.services.async_call(
            domain=DOMAIN,
            service=SERVICE_RESET,
            service_data={},
            target={"entity_id": "sensor.energy_bill"},
            blocking=True,
        )

        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    assert state
    assert state.state == "0"
    assert state.attributes.get("last_reset") == now.isoformat()
    assert state.attributes.get("last_period") == "3"

    state = hass.states.get("sensor.water_bill")
    assert state
    assert state.state == "6"
    assert state.attributes.get("last_reset") == last_reset
    assert state.attributes.get("last_period") == "0"


@pytest.mark.parametrize(
    ("yaml_config", "config_entry_config"),
    [
        (
            {
                "utility_meter": {
                    "energy_bill": {
                        "net_consumption": True,
                        "source": "sensor.energy",
                    }
                }
            },
            None,
        ),
        (
            None,
            {
                "cycle": "none",
                "delta_values": False,
                "name": "Energy bill",
                "net_consumption": True,
                "offset": 0,
                "periodically_resetting": True,
                "source": "sensor.energy",
                "tariffs": [],
            },
        ),
    ],
)
async def test_net_consumption(
    hass: HomeAssistant, yaml_config, config_entry_config
) -> None:
    """Test utility sensor state."""
    if yaml_config:
        assert await async_setup_component(hass, DOMAIN, yaml_config)
        await hass.async_block_till_done()
        entity_id = yaml_config[DOMAIN]["energy_bill"]["source"]
    else:
        config_entry = MockConfigEntry(
            data={},
            domain=DOMAIN,
            options=config_entry_config,
            title=config_entry_config["name"],
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        entity_id = config_entry_config["source"]

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)

    hass.states.async_set(
        entity_id, 2, {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR}
    )
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            1,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    assert state is not None

    assert state.state == "-1"


@pytest.mark.parametrize(
    ("yaml_config", "config_entry_config"),
    [
        (
            {
                "utility_meter": {
                    "energy_bill": {
                        "net_consumption": False,
                        "source": "sensor.energy",
                    }
                }
            },
            None,
        ),
        (
            None,
            {
                "cycle": "none",
                "delta_values": False,
                "name": "Energy bill",
                "net_consumption": False,
                "offset": 0,
                "source": "sensor.energy",
                "tariffs": [],
            },
        ),
    ],
)
async def test_non_net_consumption(
    hass: HomeAssistant,
    yaml_config,
    config_entry_config,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test utility sensor state."""
    if yaml_config:
        assert await async_setup_component(hass, DOMAIN, yaml_config)
        await hass.async_block_till_done()
        entity_id = yaml_config[DOMAIN]["energy_bill"]["source"]
    else:
        config_entry = MockConfigEntry(
            data={},
            domain=DOMAIN,
            options=config_entry_config,
            title=config_entry_config["name"],
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        entity_id = config_entry_config["source"]

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)

    hass.states.async_set(
        entity_id, 2, {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR}
    )
    await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            1,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    now = dt_util.utcnow() + timedelta(seconds=10)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            None,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()
    assert "invalid new state " in caplog.text

    state = hass.states.get("sensor.energy_bill")
    assert state is not None

    assert state.state == "0"


@pytest.mark.parametrize(
    ("yaml_config", "config_entry_config"),
    [
        (
            {
                "utility_meter": {
                    "energy_bill": {
                        "delta_values": True,
                        "source": "sensor.energy",
                    }
                }
            },
            None,
        ),
        (
            None,
            {
                "cycle": "none",
                "delta_values": True,
                "name": "Energy bill",
                "net_consumption": False,
                "offset": 0,
                "periodically_resetting": True,
                "source": "sensor.energy",
                "tariffs": [],
            },
        ),
    ],
)
async def test_delta_values(
    hass: HomeAssistant,
    yaml_config,
    config_entry_config,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test utility meter "delta_values" mode."""
    # Home assistant is not runnit yet
    hass.set_state(CoreState.not_running)

    now = dt_util.utcnow()
    with freeze_time(now):
        if yaml_config:
            assert await async_setup_component(hass, DOMAIN, yaml_config)
            await hass.async_block_till_done()
            entity_id = yaml_config[DOMAIN]["energy_bill"]["source"]
        else:
            config_entry = MockConfigEntry(
                data={},
                domain=DOMAIN,
                options=config_entry_config,
                title=config_entry_config["name"],
            )
            config_entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
            entity_id = config_entry_config["source"]

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)

        async_fire_time_changed(hass, now)
        hass.states.async_set(
            entity_id, 1, {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR}
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    assert state.attributes.get("status") == COLLECTING

    now += timedelta(seconds=30)
    with freeze_time(now):
        async_fire_time_changed(hass, now)
        hass.states.async_set(
            entity_id,
            None,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()
    assert "invalid new state from sensor.energy : None" in caplog.text

    now += timedelta(seconds=30)
    with freeze_time(now):
        async_fire_time_changed(hass, now)
        hass.states.async_set(
            entity_id,
            3,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    assert state.attributes.get("status") == COLLECTING

    now += timedelta(seconds=30)
    with freeze_time(now):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
        hass.states.async_set(
            entity_id,
            6,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    assert state is not None

    assert state.state == "10"


@pytest.mark.parametrize(
    ("yaml_config", "config_entry_config"),
    [
        (
            {
                "utility_meter": {
                    "energy_bill": {
                        "source": "sensor.energy",
                        "periodically_resetting": False,
                    }
                }
            },
            None,
        ),
        (
            None,
            {
                "cycle": "none",
                "delta_values": False,
                "name": "Energy bill",
                "net_consumption": False,
                "offset": 0,
                "periodically_resetting": False,
                "source": "sensor.energy",
                "tariffs": [],
            },
        ),
    ],
)
async def test_non_periodically_resetting(
    hass: HomeAssistant, yaml_config, config_entry_config
) -> None:
    """Test utility meter "non periodically resetting" mode."""
    # Home assistant is not runnit yet
    hass.set_state(CoreState.not_running)

    now = dt_util.utcnow()
    with freeze_time(now):
        if yaml_config:
            assert await async_setup_component(hass, DOMAIN, yaml_config)
            await hass.async_block_till_done()
            entity_id = yaml_config[DOMAIN]["energy_bill"]["source"]
        else:
            config_entry = MockConfigEntry(
                data={},
                domain=DOMAIN,
                options=config_entry_config,
                title=config_entry_config["name"],
                version=2,
            )
            config_entry.add_to_hass(hass)
            assert await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()
            entity_id = config_entry_config["source"]

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)

        async_fire_time_changed(hass, now)
        hass.states.async_set(
            entity_id, 1, {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR}
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    assert state.attributes.get("status") == COLLECTING

    now += timedelta(seconds=30)
    with freeze_time(now):
        async_fire_time_changed(hass, now)
        hass.states.async_set(
            entity_id,
            3,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    assert state.state == "2"
    assert state.attributes.get("last_valid_state") == "3"
    assert state.attributes.get("status") == COLLECTING

    now += timedelta(seconds=30)
    with freeze_time(now):
        async_fire_time_changed(hass, now)
        hass.states.async_set(
            entity_id,
            STATE_UNKNOWN,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    assert state.state == "2"
    assert state.attributes.get("last_valid_state") == "3"
    assert state.attributes.get("status") == COLLECTING

    now += timedelta(seconds=30)
    with freeze_time(now):
        async_fire_time_changed(hass, now)
        hass.states.async_set(
            entity_id,
            6,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    assert state.state == "5"
    assert state.attributes.get("last_valid_state") == "6"
    assert state.attributes.get("status") == COLLECTING

    now += timedelta(seconds=30)
    with freeze_time(now):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
        hass.states.async_set(
            entity_id,
            9,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    assert state.state == "8"
    assert state.attributes.get("last_valid_state") == "9"
    assert state.attributes.get("status") == COLLECTING


@pytest.mark.parametrize(
    ("yaml_config", "config_entry_config"),
    [
        (
            {
                "utility_meter": {
                    "energy_bill": {
                        "source": "sensor.energy",
                        "periodically_resetting": False,
                        "tariffs": ["low", "high"],
                    }
                }
            },
            None,
        ),
        (
            None,
            {
                "cycle": "none",
                "delta_values": False,
                "name": "Energy bill",
                "net_consumption": False,
                "offset": 0,
                "periodically_resetting": False,
                "source": "sensor.energy",
                "tariffs": ["low", "high"],
            },
        ),
    ],
)
async def test_non_periodically_resetting_meter_with_tariffs(
    hass: HomeAssistant, yaml_config, config_entry_config
) -> None:
    """Test test_non_periodically_resetting_meter_with_tariffs."""
    if yaml_config:
        assert await async_setup_component(hass, DOMAIN, yaml_config)
        await hass.async_block_till_done()
        entity_id = yaml_config[DOMAIN]["energy_bill"]["source"]
    else:
        config_entry = MockConfigEntry(
            data={},
            domain=DOMAIN,
            options=config_entry_config,
            title=config_entry_config["name"],
            version=2,
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        entity_id = config_entry_config["source"]

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)

    await hass.async_block_till_done()

    hass.states.async_set(
        entity_id, 2, {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR}
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_low")
    assert state is not None
    assert state.state == "0"
    assert state.attributes.get("status") == COLLECTING
    assert state.attributes.get("last_valid_state") == "2"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR

    state = hass.states.get("sensor.energy_bill_high")
    assert state is not None
    assert state.state == "0"
    assert state.attributes.get("status") == PAUSED
    assert state.attributes.get("last_valid_state") == "None"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfEnergy.KILO_WATT_HOUR

    now = dt_util.utcnow() + timedelta(seconds=10)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            3,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_low")
    assert state is not None
    assert state.state == "1"
    assert state.attributes.get("last_valid_state") == "3"
    assert state.attributes.get("status") == COLLECTING

    state = hass.states.get("sensor.energy_bill_high")
    assert state is not None
    assert state.state == "0"
    assert state.attributes.get("last_valid_state") == "None"
    assert state.attributes.get("status") == PAUSED

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.energy_bill", "option": "high"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_low")
    assert state.attributes.get("last_valid_state") == "None"
    assert state.attributes.get("status") == PAUSED

    state = hass.states.get("sensor.energy_bill_high")
    assert state.attributes.get("last_valid_state") == "None"
    assert state.attributes.get("status") == COLLECTING

    now = dt_util.utcnow() + timedelta(seconds=20)
    with freeze_time(now):
        hass.states.async_set(
            entity_id,
            6,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill_low")
    assert state is not None
    assert state.state == "1"
    assert state.attributes.get("last_valid_state") == "None"
    assert state.attributes.get("status") == PAUSED

    state = hass.states.get("sensor.energy_bill_high")
    assert state is not None
    assert state.state == "3"
    assert state.attributes.get("last_valid_state") == "6"
    assert state.attributes.get("status") == COLLECTING


def gen_config(cycle, offset=None):
    """Generate configuration."""
    config = {
        "utility_meter": {"energy_bill": {"source": "sensor.energy", "cycle": cycle}}
    }

    if offset:
        config["utility_meter"]["energy_bill"]["offset"] = {
            "days": offset.days,
            "seconds": offset.seconds,
        }
    return config


async def _test_self_reset(
    hass: HomeAssistant, config, start_time, expect_reset=True
) -> None:
    """Test energy sensor self reset."""
    now = dt_util.parse_datetime(start_time)
    with freeze_time(now):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        entity_id = config[DOMAIN]["energy_bill"]["source"]

        async_fire_time_changed(hass, now)
        hass.states.async_set(
            entity_id, 1, {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR}
        )
        await hass.async_block_till_done()

    now += timedelta(seconds=30)
    with freeze_time(now):
        async_fire_time_changed(hass, now)
        hass.states.async_set(
            entity_id,
            3,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    now += timedelta(seconds=30)
    with freeze_time(now):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
        hass.states.async_set(
            entity_id,
            6,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    if expect_reset:
        assert state.attributes.get("last_period") == "2"
        assert (
            state.attributes.get("last_reset") == dt_util.as_utc(now).isoformat()
        )  # last_reset is kept in UTC
        assert state.state == "3"
    else:
        assert state.attributes.get("last_period") == "0"
        assert state.state == "5"
        start_time_str = dt_util.parse_datetime(start_time).isoformat()
        assert state.attributes.get("last_reset") == start_time_str

    # Check next day when nothing should happen for weekly, monthly, bimonthly and yearly
    if config["utility_meter"]["energy_bill"].get("cycle") in [
        QUARTER_HOURLY,
        HOURLY,
        DAILY,
    ]:
        now += timedelta(minutes=5)
    else:
        now += timedelta(days=5)
    with freeze_time(now):
        async_fire_time_changed(hass, now)
        await hass.async_block_till_done()
        hass.states.async_set(
            entity_id,
            10,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfEnergy.KILO_WATT_HOUR},
            force_update=True,
        )
        await hass.async_block_till_done()
    state = hass.states.get("sensor.energy_bill")
    if expect_reset:
        assert state.attributes.get("last_period") == "2"
        assert state.state == "7"
    else:
        assert state.attributes.get("last_period") == "0"
        assert state.state == "9"


async def test_self_reset_cron_pattern(hass: HomeAssistant) -> None:
    """Test cron pattern reset of meter."""
    config = {
        "utility_meter": {
            "energy_bill": {"source": "sensor.energy", "cron": "0 0 1 * *"}
        }
    }

    await _test_self_reset(hass, config, "2017-01-31T23:59:00.000000+00:00")


async def test_self_reset_quarter_hourly(hass: HomeAssistant) -> None:
    """Test quarter-hourly reset of meter."""
    await _test_self_reset(
        hass, gen_config("quarter-hourly"), "2017-12-31T23:59:00.000000+00:00"
    )


async def test_self_reset_quarter_hourly_first_quarter(hass: HomeAssistant) -> None:
    """Test quarter-hourly reset of meter."""
    await _test_self_reset(
        hass, gen_config("quarter-hourly"), "2017-12-31T23:14:00.000000+00:00"
    )


async def test_self_reset_quarter_hourly_second_quarter(hass: HomeAssistant) -> None:
    """Test quarter-hourly reset of meter."""
    await _test_self_reset(
        hass, gen_config("quarter-hourly"), "2017-12-31T23:29:00.000000+00:00"
    )


async def test_self_reset_quarter_hourly_third_quarter(hass: HomeAssistant) -> None:
    """Test quarter-hourly reset of meter."""
    await _test_self_reset(
        hass, gen_config("quarter-hourly"), "2017-12-31T23:44:00.000000+00:00"
    )


async def test_self_reset_hourly(hass: HomeAssistant) -> None:
    """Test hourly reset of meter."""
    await _test_self_reset(
        hass, gen_config("hourly"), "2017-12-31T23:59:00.000000+00:00"
    )


async def test_self_reset_hourly_dst(hass: HomeAssistant) -> None:
    """Test hourly reset of meter in DST change conditions."""

    hass.config.time_zone = "Europe/Lisbon"
    dt_util.set_default_time_zone(dt_util.get_time_zone(hass.config.time_zone))
    await _test_self_reset(
        hass, gen_config("hourly"), "2023-10-29T01:59:00.000000+00:00"
    )


async def test_self_reset_daily(hass: HomeAssistant) -> None:
    """Test daily reset of meter."""
    await _test_self_reset(
        hass, gen_config("daily"), "2017-12-31T23:59:00.000000+00:00"
    )


async def test_self_reset_weekly(hass: HomeAssistant) -> None:
    """Test weekly reset of meter."""
    await _test_self_reset(
        hass, gen_config("weekly"), "2017-12-31T23:59:00.000000+00:00"
    )


async def test_self_reset_monthly(hass: HomeAssistant) -> None:
    """Test monthly reset of meter."""
    await _test_self_reset(
        hass, gen_config("monthly"), "2017-12-31T23:59:00.000000+00:00"
    )


async def test_self_reset_bimonthly(hass: HomeAssistant) -> None:
    """Test bimonthly reset of meter occurs on even months."""
    await _test_self_reset(
        hass, gen_config("bimonthly"), "2017-12-31T23:59:00.000000+00:00"
    )


async def test_self_no_reset_bimonthly(hass: HomeAssistant) -> None:
    """Test bimonthly reset of meter does not occur on odd months."""
    await _test_self_reset(
        hass,
        gen_config("bimonthly"),
        "2018-01-01T23:59:00.000000+00:00",
        expect_reset=False,
    )


async def test_self_reset_quarterly(hass: HomeAssistant) -> None:
    """Test quarterly reset of meter."""
    await _test_self_reset(
        hass, gen_config("quarterly"), "2017-03-31T23:59:00.000000+00:00"
    )


async def test_self_reset_yearly(hass: HomeAssistant) -> None:
    """Test yearly reset of meter."""
    await _test_self_reset(
        hass, gen_config("yearly"), "2017-12-31T23:59:00.000000+00:00"
    )


async def test_self_no_reset_yearly(hass: HomeAssistant) -> None:
    """Test yearly reset of meter does not occur after 1st January."""
    await _test_self_reset(
        hass,
        gen_config("yearly"),
        "2018-01-01T23:59:00.000000+00:00",
        expect_reset=False,
    )


async def test_reset_yearly_offset(hass: HomeAssistant) -> None:
    """Test yearly reset of meter."""
    await _test_self_reset(
        hass,
        gen_config("yearly", timedelta(days=1, minutes=10)),
        "2018-01-02T00:09:00.000000+00:00",
    )


async def test_no_reset_yearly_offset(hass: HomeAssistant) -> None:
    """Test yearly reset of meter."""
    await _test_self_reset(
        hass,
        gen_config("yearly", timedelta(27)),
        "2018-04-29T23:59:00.000000+00:00",
        expect_reset=False,
    )


async def test_bad_offset(hass: HomeAssistant) -> None:
    """Test bad offset of meter."""
    assert not await async_setup_component(
        hass, DOMAIN, gen_config("monthly", timedelta(days=31))
    )


def test_calculate_adjustment_invalid_new_state(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that calculate_adjustment method returns None if the new state is invalid."""
    mock_sensor = UtilityMeterSensor(
        cron_pattern=None,
        delta_values=False,
        meter_offset=DEFAULT_OFFSET,
        meter_type=DAILY,
        name="Test utility meter",
        net_consumption=False,
        parent_meter="sensor.test",
        periodically_resetting=True,
        sensor_always_available=False,
        unique_id="test_utility_meter",
        source_entity="sensor.test",
        tariff=None,
        tariff_entity=None,
    )

    new_state: State = State(entity_id="sensor.test", state="unknown")
    assert mock_sensor.calculate_adjustment(None, new_state) is None
    assert "Invalid state unknown" in caplog.text


async def test_unit_of_measurement_missing_invalid_new_state(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a suggestion is created when new_state is missing unit_of_measurement."""
    yaml_config = {
        "utility_meter": {
            "energy_bill": {
                "source": "sensor.energy",
            }
        }
    }
    source_entity_id = yaml_config[DOMAIN]["energy_bill"]["source"]

    assert await async_setup_component(hass, DOMAIN, yaml_config)
    await hass.async_block_till_done()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    hass.states.async_set(source_entity_id, 4, {ATTR_UNIT_OF_MEASUREMENT: None})

    await hass.async_block_till_done()

    state = hass.states.get("sensor.energy_bill")
    assert state is not None
    assert state.state == "0"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert (
        f"Source sensor {source_entity_id} has no unit of measurement." in caplog.text
    )


async def test_device_id(hass: HomeAssistant) -> None:
    """Test for source entity device for Utility Meter."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

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

    utility_meter_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "cycle": "monthly",
            "delta_values": False,
            "name": "Energy",
            "net_consumption": False,
            "offset": 0,
            "periodically_resetting": True,
            "source": "sensor.test_source",
            "tariffs": ["peak", "offpeak"],
        },
        title="Energy",
    )

    utility_meter_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(utility_meter_config_entry.entry_id)
    await hass.async_block_till_done()

    utility_meter_entity = entity_registry.async_get("sensor.energy_peak")
    assert utility_meter_entity is not None
    assert utility_meter_entity.device_id == source_entity.device_id

    utility_meter_entity = entity_registry.async_get("sensor.energy_offpeak")
    assert utility_meter_entity is not None
    assert utility_meter_entity.device_id == source_entity.device_id

    utility_meter_no_tariffs_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "cycle": "monthly",
            "delta_values": False,
            "name": "Energy",
            "net_consumption": False,
            "offset": 0,
            "periodically_resetting": True,
            "source": "sensor.test_source",
            "tariffs": [],
        },
        title="Energy",
    )

    utility_meter_no_tariffs_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(
        utility_meter_no_tariffs_config_entry.entry_id
    )
    await hass.async_block_till_done()

    utility_meter_no_tariffs_entity = entity_registry.async_get("sensor.energy")
    assert utility_meter_no_tariffs_entity is not None
    assert utility_meter_no_tariffs_entity.device_id == source_entity.device_id
