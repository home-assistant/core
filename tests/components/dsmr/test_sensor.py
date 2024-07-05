"""Test for DSMR components.

Tests setup of the DSMR component and ensure incoming telegrams cause
Entity to be updated with new values.

"""

import asyncio
import datetime
from decimal import Decimal
from itertools import chain, repeat
from unittest.mock import DEFAULT, MagicMock

from dsmr_parser.obis_references import (
    BELGIUM_CURRENT_AVERAGE_DEMAND,
    BELGIUM_MAXIMUM_DEMAND_MONTH,
    BELGIUM_MBUS1_DEVICE_TYPE,
    BELGIUM_MBUS1_EQUIPMENT_IDENTIFIER,
    BELGIUM_MBUS1_METER_READING1,
    BELGIUM_MBUS1_METER_READING2,
    BELGIUM_MBUS2_DEVICE_TYPE,
    BELGIUM_MBUS2_EQUIPMENT_IDENTIFIER,
    BELGIUM_MBUS2_METER_READING1,
    BELGIUM_MBUS2_METER_READING2,
    BELGIUM_MBUS3_DEVICE_TYPE,
    BELGIUM_MBUS3_EQUIPMENT_IDENTIFIER,
    BELGIUM_MBUS3_METER_READING1,
    BELGIUM_MBUS3_METER_READING2,
    BELGIUM_MBUS4_DEVICE_TYPE,
    BELGIUM_MBUS4_EQUIPMENT_IDENTIFIER,
    BELGIUM_MBUS4_METER_READING1,
    BELGIUM_MBUS4_METER_READING2,
    CURRENT_ELECTRICITY_USAGE,
    ELECTRICITY_ACTIVE_TARIFF,
    ELECTRICITY_EXPORTED_TOTAL,
    ELECTRICITY_IMPORTED_TOTAL,
    GAS_METER_READING,
    HOURLY_GAS_METER_READING,
)
from dsmr_parser.objects import CosemObject, MBusObject
import pytest

from homeassistant.components.sensor import (
    ATTR_OPTIONS,
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, patch


async def test_default_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test the default setup."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        CURRENT_ELECTRICITY_USAGE: CosemObject(
            CURRENT_ELECTRICITY_USAGE,
            [{"value": Decimal("0.0"), "unit": UnitOfPower.WATT}],
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject(
            ELECTRICITY_ACTIVE_TARIFF, [{"value": "0001", "unit": ""}]
        ),
        GAS_METER_READING: MBusObject(
            GAS_METER_READING,
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(745.695), "unit": UnitOfVolume.CUBIC_METERS},
            ],
        ),
    }

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    entry = entity_registry.async_get("sensor.electricity_meter_power_consumption")
    assert entry
    assert entry.unique_id == "1234_current_electricity_usage"

    entry = entity_registry.async_get("sensor.gas_meter_gas_consumption")
    assert entry
    assert entry.unique_id == "5678_gas_meter_reading"

    # make sure entities are initialized
    power_consumption = hass.states.get("sensor.electricity_meter_power_consumption")
    assert power_consumption.state == "0.0"
    assert (
        power_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.POWER
    )
    assert (
        power_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.MEASUREMENT
    )
    assert power_consumption.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "W"

    telegram = {
        CURRENT_ELECTRICITY_USAGE: CosemObject(
            CURRENT_ELECTRICITY_USAGE,
            [{"value": Decimal("35.0"), "unit": UnitOfPower.WATT}],
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject(
            ELECTRICITY_ACTIVE_TARIFF, [{"value": "0001", "unit": ""}]
        ),
        GAS_METER_READING: MBusObject(
            GAS_METER_READING,
            [
                {"value": datetime.datetime.fromtimestamp(1551642214)},
                {"value": Decimal(745.701), "unit": UnitOfVolume.CUBIC_METERS},
            ],
        ),
    }

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    # ensure entities have new state value after incoming telegram
    power_consumption = hass.states.get("sensor.electricity_meter_power_consumption")
    assert power_consumption.state == "35.0"
    assert power_consumption.attributes.get("unit_of_measurement") == UnitOfPower.WATT

    # tariff should be translated in human readable and have no unit
    active_tariff = hass.states.get("sensor.electricity_meter_active_tariff")
    assert active_tariff.state == "low"
    assert active_tariff.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENUM
    assert (
        active_tariff.attributes.get(ATTR_FRIENDLY_NAME)
        == "Electricity Meter Active tariff"
    )
    assert active_tariff.attributes.get(ATTR_OPTIONS) == ["low", "normal"]
    assert active_tariff.attributes.get(ATTR_STATE_CLASS) is None
    assert active_tariff.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None

    # check if gas consumption is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_meter_gas_consumption")
    assert gas_consumption.state == "745.701"
    assert gas_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.GAS
    assert (
        gas_consumption.attributes.get(ATTR_FRIENDLY_NAME)
        == "Gas Meter Gas consumption"
    )
    assert (
        gas_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        gas_consumption.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfVolume.CUBIC_METERS
    )


async def test_setup_only_energy(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test the default setup."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "serial_id": "1234",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        CURRENT_ELECTRICITY_USAGE: CosemObject(
            CURRENT_ELECTRICITY_USAGE,
            [{"value": Decimal("35.0"), "unit": UnitOfPower.WATT}],
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject(
            ELECTRICITY_ACTIVE_TARIFF, [{"value": "0001", "unit": ""}]
        ),
    }

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    entry = entity_registry.async_get("sensor.electricity_meter_power_consumption")
    assert entry
    assert entry.unique_id == "1234_current_electricity_usage"

    entry = entity_registry.async_get("sensor.gas_meter_gas_consumption")
    assert not entry


async def test_v4_meter(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Test if v4 meter is correctly parsed."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "4",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        HOURLY_GAS_METER_READING: MBusObject(
            HOURLY_GAS_METER_READING,
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(745.695), "unit": "m3"},
            ],
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject(
            ELECTRICITY_ACTIVE_TARIFF, [{"value": "0001", "unit": ""}]
        ),
    }

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    # tariff should be translated in human readable and have no unit
    active_tariff = hass.states.get("sensor.electricity_meter_active_tariff")
    assert active_tariff.state == "low"
    assert active_tariff.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENUM
    assert active_tariff.attributes.get(ATTR_OPTIONS) == ["low", "normal"]
    assert active_tariff.attributes.get(ATTR_STATE_CLASS) is None
    assert active_tariff.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None

    # check if gas consumption is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_meter_gas_consumption")
    assert gas_consumption.state == "745.695"
    assert gas_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.GAS
    assert (
        gas_consumption.attributes.get("unit_of_measurement")
        == UnitOfVolume.CUBIC_METERS
    )
    assert (
        gas_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        gas_consumption.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfVolume.CUBIC_METERS
    )


@pytest.mark.parametrize(
    ("value", "state"),
    [
        (Decimal(745.690), "745.69"),
        (Decimal(745.695), "745.695"),
        (Decimal(0.000), STATE_UNKNOWN),
    ],
)
async def test_v5_meter(
    hass: HomeAssistant,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
    value: Decimal,
    state: str,
) -> None:
    """Test if v5 meter is correctly parsed."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        HOURLY_GAS_METER_READING: MBusObject(
            HOURLY_GAS_METER_READING,
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": value, "unit": "m3"},
            ],
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject(
            ELECTRICITY_ACTIVE_TARIFF, [{"value": "0001", "unit": ""}]
        ),
    }

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    # tariff should be translated in human readable and have no unit
    active_tariff = hass.states.get("sensor.electricity_meter_active_tariff")
    assert active_tariff.state == "low"
    assert active_tariff.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENUM
    assert active_tariff.attributes.get(ATTR_OPTIONS) == ["low", "normal"]
    assert active_tariff.attributes.get(ATTR_STATE_CLASS) is None
    assert active_tariff.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None

    # check if gas consumption is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_meter_gas_consumption")
    assert gas_consumption.state == state
    assert gas_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.GAS
    assert (
        gas_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        gas_consumption.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfVolume.CUBIC_METERS
    )


async def test_luxembourg_meter(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Test if v5 meter is correctly parsed."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5L",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        HOURLY_GAS_METER_READING: MBusObject(
            HOURLY_GAS_METER_READING,
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(745.695), "unit": "m3"},
            ],
        ),
        ELECTRICITY_IMPORTED_TOTAL: CosemObject(
            ELECTRICITY_IMPORTED_TOTAL,
            [{"value": Decimal(123.456), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
        ELECTRICITY_EXPORTED_TOTAL: CosemObject(
            ELECTRICITY_EXPORTED_TOTAL,
            [{"value": Decimal(654.321), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
    }

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    active_tariff = hass.states.get("sensor.electricity_meter_energy_consumption_total")
    assert active_tariff.state == "123.456"
    assert active_tariff.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert (
        active_tariff.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        active_tariff.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfEnergy.KILO_WATT_HOUR
    )

    active_tariff = hass.states.get("sensor.electricity_meter_energy_production_total")
    assert active_tariff.state == "654.321"
    assert (
        active_tariff.attributes.get("unit_of_measurement")
        == UnitOfEnergy.KILO_WATT_HOUR
    )

    # check if gas consumption is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_meter_gas_consumption")
    assert gas_consumption.state == "745.695"
    assert gas_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.GAS
    assert (
        gas_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        gas_consumption.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfVolume.CUBIC_METERS
    )


async def test_belgian_meter(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Test if Belgian meter is correctly parsed."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5B",
        "serial_id": "1234",
        "serial_id_gas": None,
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        BELGIUM_CURRENT_AVERAGE_DEMAND: CosemObject(
            BELGIUM_CURRENT_AVERAGE_DEMAND,
            [{"value": Decimal(1.75), "unit": "kW"}],
        ),
        BELGIUM_MAXIMUM_DEMAND_MONTH: MBusObject(
            BELGIUM_MAXIMUM_DEMAND_MONTH,
            [
                {"value": datetime.datetime.fromtimestamp(1551642218)},
                {"value": Decimal(4.11), "unit": "kW"},
            ],
        ),
        BELGIUM_MBUS1_DEVICE_TYPE: CosemObject(
            BELGIUM_MBUS1_DEVICE_TYPE, [{"value": "003", "unit": ""}]
        ),
        BELGIUM_MBUS1_EQUIPMENT_IDENTIFIER: CosemObject(
            BELGIUM_MBUS1_EQUIPMENT_IDENTIFIER,
            [{"value": "37464C4F32313139303333373331", "unit": ""}],
        ),
        BELGIUM_MBUS1_METER_READING2: MBusObject(
            BELGIUM_MBUS1_METER_READING2,
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(745.695), "unit": "m3"},
            ],
        ),
        BELGIUM_MBUS2_DEVICE_TYPE: CosemObject(
            BELGIUM_MBUS2_DEVICE_TYPE, [{"value": "007", "unit": ""}]
        ),
        BELGIUM_MBUS2_EQUIPMENT_IDENTIFIER: CosemObject(
            BELGIUM_MBUS2_EQUIPMENT_IDENTIFIER,
            [{"value": "37464C4F32313139303333373332", "unit": ""}],
        ),
        BELGIUM_MBUS2_METER_READING1: MBusObject(
            BELGIUM_MBUS2_METER_READING1,
            [
                {"value": datetime.datetime.fromtimestamp(1551642214)},
                {"value": Decimal(678.695), "unit": "m3"},
            ],
        ),
        BELGIUM_MBUS3_DEVICE_TYPE: CosemObject(
            BELGIUM_MBUS3_DEVICE_TYPE, [{"value": "003", "unit": ""}]
        ),
        BELGIUM_MBUS3_EQUIPMENT_IDENTIFIER: CosemObject(
            BELGIUM_MBUS3_EQUIPMENT_IDENTIFIER,
            [{"value": "37464C4F32313139303333373333", "unit": ""}],
        ),
        BELGIUM_MBUS3_METER_READING2: MBusObject(
            BELGIUM_MBUS3_METER_READING2,
            [
                {"value": datetime.datetime.fromtimestamp(1551642215)},
                {"value": Decimal(12.12), "unit": "m3"},
            ],
        ),
        BELGIUM_MBUS4_DEVICE_TYPE: CosemObject(
            BELGIUM_MBUS4_DEVICE_TYPE, [{"value": "007", "unit": ""}]
        ),
        BELGIUM_MBUS4_EQUIPMENT_IDENTIFIER: CosemObject(
            BELGIUM_MBUS4_EQUIPMENT_IDENTIFIER,
            [{"value": "37464C4F32313139303333373334", "unit": ""}],
        ),
        BELGIUM_MBUS4_METER_READING1: MBusObject(
            BELGIUM_MBUS4_METER_READING1,
            [
                {"value": datetime.datetime.fromtimestamp(1551642216)},
                {"value": Decimal(13.13), "unit": "m3"},
            ],
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject(
            ELECTRICITY_ACTIVE_TARIFF, [{"value": "0001", "unit": ""}]
        ),
    }

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    # tariff should be translated in human readable and have no unit
    active_tariff = hass.states.get("sensor.electricity_meter_active_tariff")
    assert active_tariff.state == "normal"
    assert active_tariff.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENUM
    assert active_tariff.attributes.get(ATTR_OPTIONS) == ["low", "normal"]
    assert active_tariff.attributes.get(ATTR_STATE_CLASS) is None
    assert active_tariff.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None

    # check current average demand is parsed correctly
    avg_demand = hass.states.get("sensor.electricity_meter_current_average_demand")
    assert avg_demand.state == "1.75"
    assert avg_demand.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.KILO_WATT
    assert avg_demand.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    # check max average demand is parsed correctly
    max_demand = hass.states.get(
        "sensor.electricity_meter_maximum_demand_current_month"
    )
    assert max_demand.state == "4.11"
    assert max_demand.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfPower.KILO_WATT
    assert max_demand.attributes.get(ATTR_STATE_CLASS) == SensorStateClass.MEASUREMENT

    # check if gas consumption mbus1 is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_meter_gas_consumption")
    assert gas_consumption.state == "745.695"
    assert gas_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.GAS
    assert (
        gas_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        gas_consumption.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfVolume.CUBIC_METERS
    )

    # check if water usage mbus2 is parsed correctly
    water_consumption = hass.states.get("sensor.water_meter_water_consumption")
    assert water_consumption.state == "678.695"
    assert (
        water_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.WATER
    )
    assert (
        water_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        water_consumption.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfVolume.CUBIC_METERS
    )

    # check if gas consumption mbus1 is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_meter_gas_consumption_2")
    assert gas_consumption.state == "12.12"
    assert gas_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.GAS
    assert (
        gas_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        gas_consumption.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfVolume.CUBIC_METERS
    )

    # check if water usage mbus2 is parsed correctly
    water_consumption = hass.states.get("sensor.water_meter_water_consumption_2")
    assert water_consumption.state == "13.13"
    assert (
        water_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.WATER
    )
    assert (
        water_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        water_consumption.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfVolume.CUBIC_METERS
    )


async def test_belgian_meter_alt(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Test if Belgian meter is correctly parsed."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5B",
        "serial_id": "1234",
        "serial_id_gas": None,
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        BELGIUM_MBUS1_DEVICE_TYPE: CosemObject(
            BELGIUM_MBUS1_DEVICE_TYPE, [{"value": "007", "unit": ""}]
        ),
        BELGIUM_MBUS1_EQUIPMENT_IDENTIFIER: CosemObject(
            BELGIUM_MBUS1_EQUIPMENT_IDENTIFIER,
            [{"value": "37464C4F32313139303333373331", "unit": ""}],
        ),
        BELGIUM_MBUS1_METER_READING1: MBusObject(
            BELGIUM_MBUS1_METER_READING1,
            [
                {"value": datetime.datetime.fromtimestamp(1551642215)},
                {"value": Decimal(123.456), "unit": "m3"},
            ],
        ),
        BELGIUM_MBUS2_DEVICE_TYPE: CosemObject(
            BELGIUM_MBUS2_DEVICE_TYPE, [{"value": "003", "unit": ""}]
        ),
        BELGIUM_MBUS2_EQUIPMENT_IDENTIFIER: CosemObject(
            BELGIUM_MBUS2_EQUIPMENT_IDENTIFIER,
            [{"value": "37464C4F32313139303333373332", "unit": ""}],
        ),
        BELGIUM_MBUS2_METER_READING2: MBusObject(
            BELGIUM_MBUS2_METER_READING2,
            [
                {"value": datetime.datetime.fromtimestamp(1551642216)},
                {"value": Decimal(678.901), "unit": "m3"},
            ],
        ),
        BELGIUM_MBUS3_DEVICE_TYPE: CosemObject(
            BELGIUM_MBUS3_DEVICE_TYPE, [{"value": "007", "unit": ""}]
        ),
        BELGIUM_MBUS3_EQUIPMENT_IDENTIFIER: CosemObject(
            BELGIUM_MBUS3_EQUIPMENT_IDENTIFIER,
            [{"value": "37464C4F32313139303333373333", "unit": ""}],
        ),
        BELGIUM_MBUS3_METER_READING1: MBusObject(
            BELGIUM_MBUS3_METER_READING1,
            [
                {"value": datetime.datetime.fromtimestamp(1551642217)},
                {"value": Decimal(12.12), "unit": "m3"},
            ],
        ),
        BELGIUM_MBUS4_DEVICE_TYPE: CosemObject(
            BELGIUM_MBUS4_DEVICE_TYPE, [{"value": "003", "unit": ""}]
        ),
        BELGIUM_MBUS4_EQUIPMENT_IDENTIFIER: CosemObject(
            BELGIUM_MBUS4_EQUIPMENT_IDENTIFIER,
            [{"value": "37464C4F32313139303333373334", "unit": ""}],
        ),
        BELGIUM_MBUS4_METER_READING2: MBusObject(
            BELGIUM_MBUS4_METER_READING2,
            [
                {"value": datetime.datetime.fromtimestamp(1551642218)},
                {"value": Decimal(13.13), "unit": "m3"},
            ],
        ),
    }

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    # check if water usage mbus1 is parsed correctly
    water_consumption = hass.states.get("sensor.water_meter_water_consumption")
    assert water_consumption.state == "123.456"
    assert (
        water_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.WATER
    )
    assert (
        water_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        water_consumption.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfVolume.CUBIC_METERS
    )

    # check if gas consumption mbus2 is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_meter_gas_consumption")
    assert gas_consumption.state == "678.901"
    assert gas_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.GAS
    assert (
        gas_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        gas_consumption.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfVolume.CUBIC_METERS
    )

    # check if water usage mbus3 is parsed correctly
    water_consumption = hass.states.get("sensor.water_meter_water_consumption_2")
    assert water_consumption.state == "12.12"
    assert (
        water_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.WATER
    )
    assert (
        water_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        water_consumption.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfVolume.CUBIC_METERS
    )

    # check if gas consumption mbus4 is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_meter_gas_consumption_2")
    assert gas_consumption.state == "13.13"
    assert gas_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.GAS
    assert (
        gas_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        gas_consumption.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfVolume.CUBIC_METERS
    )


async def test_belgian_meter_mbus(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Test if Belgian meter is correctly parsed."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5B",
        "serial_id": "1234",
        "serial_id_gas": None,
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        ELECTRICITY_ACTIVE_TARIFF: CosemObject(
            ELECTRICITY_ACTIVE_TARIFF, [{"value": "0003", "unit": ""}]
        ),
        BELGIUM_MBUS1_DEVICE_TYPE: CosemObject(
            BELGIUM_MBUS1_DEVICE_TYPE, [{"value": "006", "unit": ""}]
        ),
        BELGIUM_MBUS1_EQUIPMENT_IDENTIFIER: CosemObject(
            BELGIUM_MBUS1_EQUIPMENT_IDENTIFIER,
            [{"value": "37464C4F32313139303333373331", "unit": ""}],
        ),
        BELGIUM_MBUS2_DEVICE_TYPE: CosemObject(
            BELGIUM_MBUS2_DEVICE_TYPE, [{"value": "003", "unit": ""}]
        ),
        BELGIUM_MBUS2_EQUIPMENT_IDENTIFIER: CosemObject(
            BELGIUM_MBUS2_EQUIPMENT_IDENTIFIER,
            [{"value": "37464C4F32313139303333373332", "unit": ""}],
        ),
        BELGIUM_MBUS3_DEVICE_TYPE: CosemObject(
            BELGIUM_MBUS3_DEVICE_TYPE, [{"value": "007", "unit": ""}]
        ),
        BELGIUM_MBUS3_EQUIPMENT_IDENTIFIER: CosemObject(
            BELGIUM_MBUS3_EQUIPMENT_IDENTIFIER,
            [{"value": "37464C4F32313139303333373333", "unit": ""}],
        ),
        BELGIUM_MBUS3_METER_READING2: MBusObject(
            BELGIUM_MBUS3_METER_READING2,
            [
                {"value": datetime.datetime.fromtimestamp(1551642217)},
                {"value": Decimal(12.12), "unit": "m3"},
            ],
        ),
        BELGIUM_MBUS4_DEVICE_TYPE: CosemObject(
            BELGIUM_MBUS4_DEVICE_TYPE, [{"value": "007", "unit": ""}]
        ),
        BELGIUM_MBUS4_METER_READING1: MBusObject(
            BELGIUM_MBUS4_METER_READING1,
            [
                {"value": datetime.datetime.fromtimestamp(1551642218)},
                {"value": Decimal(13.13), "unit": "m3"},
            ],
        ),
    }

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    # tariff should be translated in human readable and have no unit
    active_tariff = hass.states.get("sensor.electricity_meter_active_tariff")
    assert active_tariff.state == "unknown"

    # check if gas consumption mbus2 is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_meter_gas_consumption")
    assert gas_consumption is None

    # check if water usage mbus3 is parsed correctly
    water_consumption = hass.states.get("sensor.water_meter_water_consumption_2")
    assert water_consumption is None

    # check if gas consumption mbus4 is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_meter_gas_consumption_2")
    assert gas_consumption is None

    # check if gas consumption mbus4 is parsed correctly
    water_consumption = hass.states.get("sensor.water_meter_water_consumption")
    assert water_consumption.state == "13.13"
    assert (
        water_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.WATER
    )
    assert (
        water_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        water_consumption.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfVolume.CUBIC_METERS
    )


async def test_belgian_meter_low(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Test if Belgian meter is correctly parsed."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5B",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        ELECTRICITY_ACTIVE_TARIFF: CosemObject(
            ELECTRICITY_ACTIVE_TARIFF, [{"value": "0002", "unit": ""}]
        )
    }

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    # tariff should be translated in human readable and have no unit
    active_tariff = hass.states.get("sensor.electricity_meter_active_tariff")
    assert active_tariff.state == "low"
    assert active_tariff.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENUM
    assert active_tariff.attributes.get(ATTR_OPTIONS) == ["low", "normal"]
    assert active_tariff.attributes.get(ATTR_STATE_CLASS) is None
    assert active_tariff.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None


async def test_swedish_meter(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Test if v5 meter is correctly parsed."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5S",
        "serial_id": None,
        "serial_id_gas": None,
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        ELECTRICITY_IMPORTED_TOTAL: CosemObject(
            ELECTRICITY_IMPORTED_TOTAL,
            [{"value": Decimal(123.456), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
        ELECTRICITY_EXPORTED_TOTAL: CosemObject(
            ELECTRICITY_EXPORTED_TOTAL,
            [{"value": Decimal(654.321), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
    }

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    active_tariff = hass.states.get("sensor.electricity_meter_energy_consumption_total")
    assert active_tariff.state == "123.456"
    assert active_tariff.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert (
        active_tariff.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        active_tariff.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfEnergy.KILO_WATT_HOUR
    )

    active_tariff = hass.states.get("sensor.electricity_meter_energy_production_total")
    assert active_tariff.state == "654.321"
    assert (
        active_tariff.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        active_tariff.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfEnergy.KILO_WATT_HOUR
    )


async def test_easymeter(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Test if Q3D meter is correctly parsed."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "Q3D",
        "serial_id": None,
        "serial_id_gas": None,
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        ELECTRICITY_IMPORTED_TOTAL: CosemObject(
            ELECTRICITY_IMPORTED_TOTAL,
            [{"value": Decimal(54184.6316), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
        ELECTRICITY_EXPORTED_TOTAL: CosemObject(
            ELECTRICITY_EXPORTED_TOTAL,
            [{"value": Decimal(19981.1069), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
    }

    mock_entry = MockConfigEntry(
        domain="dsmr",
        unique_id="/dev/ttyUSB0",
        data=entry_data,
        options=entry_options,
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    active_tariff = hass.states.get("sensor.electricity_meter_energy_consumption_total")
    assert active_tariff.state == "54184.632"
    assert active_tariff.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert (
        active_tariff.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        active_tariff.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfEnergy.KILO_WATT_HOUR
    )

    active_tariff = hass.states.get("sensor.electricity_meter_energy_production_total")
    assert active_tariff.state == "19981.107"
    assert (
        active_tariff.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        active_tariff.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfEnergy.KILO_WATT_HOUR
    )


async def test_tcp(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """If proper config provided TCP connection should be made."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "host": "localhost",
        "port": "1234",
        "dsmr_version": "2.2",
        "protocol": "dsmr_protocol",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert connection_factory.call_args_list[0][0][0] == "localhost"
    assert connection_factory.call_args_list[0][0][1] == "1234"


async def test_rfxtrx_tcp(
    hass: HomeAssistant,
    rfxtrx_dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """If proper config provided RFXtrx TCP connection should be made."""
    (connection_factory, transport, protocol) = rfxtrx_dsmr_connection_fixture

    entry_data = {
        "host": "localhost",
        "port": "1234",
        "dsmr_version": "2.2",
        "protocol": "rfxtrx_dsmr_protocol",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert connection_factory.call_args_list[0][0][0] == "localhost"
    assert connection_factory.call_args_list[0][0][1] == "1234"


@patch("homeassistant.components.dsmr.sensor.DEFAULT_RECONNECT_INTERVAL", 0)
async def test_connection_errors_retry(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Connection should be retried on error during setup."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }

    # override the mock to have it fail the first time and succeed after
    first_fail_connection_factory = MagicMock(
        return_value=(transport, protocol),
        side_effect=chain([TimeoutError], repeat(DEFAULT)),
    )

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data
    )

    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dsmr.sensor.create_dsmr_reader",
        first_fail_connection_factory,
    ):
        await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

        # wait for sleep to resolve
        await hass.async_block_till_done()
        assert first_fail_connection_factory.call_count >= 2, "connecting not retried"


@patch("homeassistant.components.dsmr.sensor.DEFAULT_RECONNECT_INTERVAL", 0)
async def test_reconnect(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """If transport disconnects, the connection should be retried."""

    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        CURRENT_ELECTRICITY_USAGE: CosemObject(
            CURRENT_ELECTRICITY_USAGE,
            [{"value": Decimal("35.0"), "unit": UnitOfPower.WATT}],
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject(
            ELECTRICITY_ACTIVE_TARIFF, [{"value": "0001", "unit": ""}]
        ),
    }

    # mock waiting coroutine while connection lasts
    closed = asyncio.Event()
    # Handshake so that `hass.async_block_till_done()` doesn't cycle forever
    closed2 = asyncio.Event()

    async def wait_closed():
        await closed.wait()
        closed2.set()

    protocol.wait_closed = wait_closed

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    assert connection_factory.call_count == 1

    state = hass.states.get("sensor.electricity_meter_power_consumption")
    assert state
    assert state.state == "35.0"

    # indicate disconnect, release wait lock and allow reconnect to happen
    closed.set()
    # wait for lock set to resolve
    await closed2.wait()
    closed2.clear()
    closed.clear()

    await hass.async_block_till_done()

    assert connection_factory.call_count >= 2, "connecting not retried"
    # setting it so teardown can be successful
    closed.set()

    await hass.config_entries.async_unload(mock_entry.entry_id)

    assert mock_entry.state is ConfigEntryState.NOT_LOADED


async def test_gas_meter_providing_energy_reading(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Test that gas providing energy readings use the correct device class."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        GAS_METER_READING: MBusObject(
            GAS_METER_READING,
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(123.456), "unit": UnitOfEnergy.GIGA_JOULE},
            ],
        ),
    }

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]
    telegram_callback(telegram)
    await hass.async_block_till_done()

    gas_consumption = hass.states.get("sensor.gas_meter_gas_consumption")
    assert gas_consumption.state == "123.456"
    assert gas_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    assert (
        gas_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )
    assert (
        gas_consumption.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfEnergy.GIGA_JOULE
    )
