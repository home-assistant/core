"""Test for DSMR components.

Tests setup of the DSMR component and ensure incoming telegrams cause
Entity to be updated with new values.

"""

import asyncio
from collections.abc import Callable
import datetime
from decimal import Decimal
from itertools import chain, repeat
from unittest.mock import DEFAULT, MagicMock

from dsmr_parser import obis_references
from dsmr_parser.obis_references import (
    BELGIUM_CURRENT_AVERAGE_DEMAND,
    BELGIUM_MAXIMUM_DEMAND_MONTH,
    CURRENT_ELECTRICITY_USAGE,
    ELECTRICITY_ACTIVE_TARIFF,
    ELECTRICITY_EXPORTED_TOTAL,
    ELECTRICITY_IMPORTED_TOTAL,
    ELECTRICITY_USED_TARIFF_1,
    ELECTRICITY_USED_TARIFF_3,
    GAS_METER_READING,
    HOURLY_GAS_METER_READING,
    INSTANTANEOUS_CURRENT_L1,
    INSTANTANEOUS_VOLTAGE_L1,
    MBUS_DEVICE_TYPE,
    MBUS_EQUIPMENT_IDENTIFIER,
    MBUS_METER_READING,
)
from dsmr_parser.objects import CosemObject, MBusObject, Telegram
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.dsmr.sensor import SENSORS, SENSORS_MBUS_DEVICE_TYPE
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
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, patch


async def test_default_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test the default setup."""
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        CURRENT_ELECTRICITY_USAGE,
        CosemObject(
            (0, 0),
            [{"value": Decimal("0.0"), "unit": UnitOfPower.WATT}],
        ),
        "CURRENT_ELECTRICITY_USAGE",
    )
    telegram.add(
        ELECTRICITY_ACTIVE_TARIFF,
        CosemObject((0, 0), [{"value": "0001", "unit": ""}]),
        "ELECTRICITY_ACTIVE_TARIFF",
    )
    telegram.add(
        GAS_METER_READING,
        MBusObject(
            (0, 0),
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal("745.695"), "unit": UnitOfVolume.CUBIC_METERS},
            ],
        ),
        "GAS_METER_READING",
    )

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

    telegram = Telegram()
    telegram.add(
        CURRENT_ELECTRICITY_USAGE,
        CosemObject(
            (0, 0),
            [{"value": Decimal("35.0"), "unit": UnitOfPower.WATT}],
        ),
        "CURRENT_ELECTRICITY_USAGE",
    )
    telegram.add(
        ELECTRICITY_ACTIVE_TARIFF,
        CosemObject((0, 0), [{"value": "0001", "unit": ""}]),
        "ELECTRICITY_ACTIVE_TARIFF",
    )
    telegram.add(
        GAS_METER_READING,
        MBusObject(
            (0, 0),
            [
                {"value": datetime.datetime.fromtimestamp(1551642214)},
                {"value": Decimal("745.701"), "unit": UnitOfVolume.CUBIC_METERS},
            ],
        ),
        "GAS_METER_READING",
    )

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
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "serial_id": "1234",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        CURRENT_ELECTRICITY_USAGE,
        CosemObject(
            (0, 0),
            [{"value": Decimal("35.0"), "unit": UnitOfPower.WATT}],
        ),
        "CURRENT_ELECTRICITY_USAGE",
    )
    telegram.add(
        ELECTRICITY_ACTIVE_TARIFF,
        CosemObject((0, 0), [{"value": "0001", "unit": ""}]),
        "ELECTRICITY_ACTIVE_TARIFF",
    )

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
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "4",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        HOURLY_GAS_METER_READING,
        MBusObject(
            (0, 0),
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal("745.695"), "unit": "m3"},
            ],
        ),
        "HOURLY_GAS_METER_READING",
    )
    telegram.add(
        ELECTRICITY_ACTIVE_TARIFF,
        CosemObject((0, 0), [{"value": "0001", "unit": ""}]),
        "ELECTRICITY_ACTIVE_TARIFF",
    )

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
        (Decimal("745.690"), "745.69"),
        (Decimal("745.695"), "745.695"),
        (Decimal("0.000"), STATE_UNKNOWN),
    ],
)
async def test_v5_meter(
    hass: HomeAssistant,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
    value: Decimal,
    state: str,
) -> None:
    """Test if v5 meter is correctly parsed."""
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        HOURLY_GAS_METER_READING,
        MBusObject(
            (0, 0),
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": value, "unit": "m3"},
            ],
        ),
        "HOURLY_GAS_METER_READING",
    )
    telegram.add(
        ELECTRICITY_ACTIVE_TARIFF,
        CosemObject((0, 0), [{"value": "0001", "unit": ""}]),
        "ELECTRICITY_ACTIVE_TARIFF",
    )

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
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5L",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        HOURLY_GAS_METER_READING,
        MBusObject(
            (0, 0),
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal("745.695"), "unit": "m3"},
            ],
        ),
        "HOURLY_GAS_METER_READING",
    )
    telegram.add(
        ELECTRICITY_IMPORTED_TOTAL,
        CosemObject(
            (0, 0),
            [{"value": Decimal("123.456"), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
        "ELECTRICITY_IMPORTED_TOTAL",
    )
    telegram.add(
        ELECTRICITY_EXPORTED_TOTAL,
        CosemObject(
            (0, 0),
            [{"value": Decimal("654.321"), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
        "ELECTRICITY_EXPORTED_TOTAL",
    )

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


async def test_eonhu_meter(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Test if v5 meter is correctly parsed."""
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5EONHU",
        "serial_id": "1234",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        ELECTRICITY_IMPORTED_TOTAL,
        CosemObject(
            (0, 0),
            [{"value": Decimal("123.456"), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
        "ELECTRICITY_IMPORTED_TOTAL",
    )
    telegram.add(
        ELECTRICITY_EXPORTED_TOTAL,
        CosemObject(
            (0, 0),
            [{"value": Decimal("654.321"), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
        "ELECTRICITY_EXPORTED_TOTAL",
    )

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


async def test_belgian_meter(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Test if Belgian meter is correctly parsed."""
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5B",
        "serial_id": "1234",
        "serial_id_gas": None,
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        BELGIUM_CURRENT_AVERAGE_DEMAND,
        CosemObject(
            (0, 0),
            [{"value": Decimal("1.75"), "unit": "kW"}],
        ),
        "BELGIUM_CURRENT_AVERAGE_DEMAND",
    )
    telegram.add(
        BELGIUM_MAXIMUM_DEMAND_MONTH,
        MBusObject(
            (0, 0),
            [
                {"value": datetime.datetime.fromtimestamp(1551642218)},
                {"value": Decimal("4.11"), "unit": "kW"},
            ],
        ),
        "BELGIUM_MAXIMUM_DEMAND_MONTH",
    )
    telegram.add(
        MBUS_DEVICE_TYPE,
        CosemObject((0, 1), [{"value": "003", "unit": ""}]),
        "MBUS_DEVICE_TYPE",
    )
    telegram.add(
        MBUS_EQUIPMENT_IDENTIFIER,
        CosemObject(
            (0, 1),
            [{"value": "37464C4F32313139303333373331", "unit": ""}],
        ),
        "MBUS_EQUIPMENT_IDENTIFIER",
    )
    telegram.add(
        MBUS_METER_READING,
        MBusObject(
            (0, 1),
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal("745.695"), "unit": "m3"},
            ],
        ),
        "MBUS_METER_READING",
    )
    telegram.add(
        MBUS_DEVICE_TYPE,
        CosemObject((0, 2), [{"value": "007", "unit": ""}]),
        "MBUS_DEVICE_TYPE",
    )
    telegram.add(
        MBUS_EQUIPMENT_IDENTIFIER,
        CosemObject(
            (0, 2),
            [{"value": "37464C4F32313139303333373332", "unit": ""}],
        ),
        "MBUS_EQUIPMENT_IDENTIFIER",
    )
    telegram.add(
        MBUS_METER_READING,
        MBusObject(
            (0, 2),
            [
                {"value": datetime.datetime.fromtimestamp(1551642214)},
                {"value": Decimal("678.695"), "unit": "m3"},
            ],
        ),
        "MBUS_METER_READING",
    )
    telegram.add(
        MBUS_DEVICE_TYPE,
        CosemObject((0, 3), [{"value": "003", "unit": ""}]),
        "MBUS_DEVICE_TYPE",
    )
    telegram.add(
        MBUS_EQUIPMENT_IDENTIFIER,
        CosemObject(
            (0, 3),
            [{"value": "37464C4F32313139303333373333", "unit": ""}],
        ),
        "MBUS_EQUIPMENT_IDENTIFIER",
    )
    telegram.add(
        MBUS_METER_READING,
        MBusObject(
            (0, 3),
            [
                {"value": datetime.datetime.fromtimestamp(1551642215)},
                {"value": Decimal("12.12"), "unit": "m3"},
            ],
        ),
        "MBUS_METER_READING",
    )
    telegram.add(
        MBUS_DEVICE_TYPE,
        CosemObject((0, 4), [{"value": "007", "unit": ""}]),
        "MBUS_DEVICE_TYPE",
    )
    telegram.add(
        MBUS_EQUIPMENT_IDENTIFIER,
        CosemObject(
            (0, 4),
            [{"value": "37464C4F32313139303333373334", "unit": ""}],
        ),
        "MBUS_EQUIPMENT_IDENTIFIER",
    )
    telegram.add(
        MBUS_METER_READING,
        MBusObject(
            (0, 4),
            [
                {"value": datetime.datetime.fromtimestamp(1551642216)},
                {"value": Decimal("13.13"), "unit": "m3"},
            ],
        ),
        "MBUS_METER_READING",
    )
    telegram.add(
        ELECTRICITY_ACTIVE_TARIFF,
        CosemObject((0, 0), [{"value": "0001", "unit": ""}]),
        "ELECTRICITY_ACTIVE_TARIFF",
    )

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
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5B",
        "serial_id": "1234",
        "serial_id_gas": None,
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        MBUS_DEVICE_TYPE,
        CosemObject((0, 1), [{"value": "007", "unit": ""}]),
        "MBUS_DEVICE_TYPE",
    )
    telegram.add(
        MBUS_EQUIPMENT_IDENTIFIER,
        CosemObject(
            (0, 1),
            [{"value": "37464C4F32313139303333373331", "unit": ""}],
        ),
        "MBUS_EQUIPMENT_IDENTIFIER",
    )
    telegram.add(
        MBUS_METER_READING,
        MBusObject(
            (0, 1),
            [
                {"value": datetime.datetime.fromtimestamp(1551642215)},
                {"value": Decimal("123.456"), "unit": "m3"},
            ],
        ),
        "MBUS_METER_READING",
    )
    telegram.add(
        MBUS_DEVICE_TYPE,
        CosemObject((0, 2), [{"value": "003", "unit": ""}]),
        "MBUS_DEVICE_TYPE",
    )
    telegram.add(
        MBUS_EQUIPMENT_IDENTIFIER,
        CosemObject(
            (0, 2),
            [{"value": "37464C4F32313139303333373332", "unit": ""}],
        ),
        "MBUS_EQUIPMENT_IDENTIFIER",
    )
    telegram.add(
        MBUS_METER_READING,
        MBusObject(
            (0, 2),
            [
                {"value": datetime.datetime.fromtimestamp(1551642216)},
                {"value": Decimal("678.901"), "unit": "m3"},
            ],
        ),
        "MBUS_METER_READING",
    )
    telegram.add(
        MBUS_DEVICE_TYPE,
        CosemObject((0, 3), [{"value": "007", "unit": ""}]),
        "MBUS_DEVICE_TYPE",
    )
    telegram.add(
        MBUS_EQUIPMENT_IDENTIFIER,
        CosemObject(
            (0, 3),
            [{"value": "37464C4F32313139303333373333", "unit": ""}],
        ),
        "MBUS_EQUIPMENT_IDENTIFIER",
    )
    telegram.add(
        MBUS_METER_READING,
        MBusObject(
            (0, 3),
            [
                {"value": datetime.datetime.fromtimestamp(1551642217)},
                {"value": Decimal("12.12"), "unit": "m3"},
            ],
        ),
        "MBUS_METER_READING",
    )
    telegram.add(
        MBUS_DEVICE_TYPE,
        CosemObject((0, 4), [{"value": "003", "unit": ""}]),
        "MBUS_DEVICE_TYPE",
    )
    telegram.add(
        MBUS_EQUIPMENT_IDENTIFIER,
        CosemObject(
            (0, 4),
            [{"value": "37464C4F32313139303333373334", "unit": ""}],
        ),
        "MBUS_EQUIPMENT_IDENTIFIER",
    )
    telegram.add(
        MBUS_METER_READING,
        MBusObject(
            (0, 4),
            [
                {"value": datetime.datetime.fromtimestamp(1551642218)},
                {"value": Decimal("13.13"), "unit": "m3"},
            ],
        ),
        "MBUS_METER_READING",
    )

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
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5B",
        "serial_id": "1234",
        "serial_id_gas": None,
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        ELECTRICITY_ACTIVE_TARIFF,
        CosemObject((0, 0), [{"value": "0003", "unit": ""}]),
        "ELECTRICITY_ACTIVE_TARIFF",
    )
    telegram.add(
        MBUS_DEVICE_TYPE,
        CosemObject((0, 1), [{"value": "006", "unit": ""}]),
        "MBUS_DEVICE_TYPE",
    )
    telegram.add(
        MBUS_EQUIPMENT_IDENTIFIER,
        CosemObject(
            (0, 1),
            [{"value": "37464C4F32313139303333373331", "unit": ""}],
        ),
        "MBUS_EQUIPMENT_IDENTIFIER",
    )
    telegram.add(
        MBUS_DEVICE_TYPE,
        CosemObject((0, 2), [{"value": "003", "unit": ""}]),
        "MBUS_DEVICE_TYPE",
    )
    telegram.add(
        MBUS_EQUIPMENT_IDENTIFIER,
        CosemObject(
            (0, 2),
            [{"value": "37464C4F32313139303333373332", "unit": ""}],
        ),
        "MBUS_EQUIPMENT_IDENTIFIER",
    )
    telegram.add(
        MBUS_DEVICE_TYPE,
        CosemObject((0, 3), [{"value": "007", "unit": ""}]),
        "MBUS_DEVICE_TYPE",
    )
    telegram.add(
        MBUS_EQUIPMENT_IDENTIFIER,
        CosemObject(
            (0, 3),
            [{"value": "37464C4F32313139303333373333", "unit": ""}],
        ),
        "MBUS_EQUIPMENT_IDENTIFIER",
    )
    telegram.add(
        MBUS_METER_READING,
        MBusObject(
            (0, 3),
            [
                {"value": datetime.datetime.fromtimestamp(1551642217)},
                {"value": Decimal("12.12"), "unit": "m3"},
            ],
        ),
        "MBUS_METER_READING",
    )
    telegram.add(
        MBUS_DEVICE_TYPE,
        CosemObject((0, 4), [{"value": "007", "unit": ""}]),
        "MBUS_DEVICE_TYPE",
    )
    telegram.add(
        MBUS_METER_READING,
        MBusObject(
            (0, 4),
            [
                {"value": datetime.datetime.fromtimestamp(1551642218)},
                {"value": Decimal("13.13"), "unit": "m3"},
            ],
        ),
        "MBUS_METER_READING",
    )

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

    # check if gas consumption mbus1 is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_meter_gas_consumption")
    assert gas_consumption is None

    # check if gas consumption mbus2 is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_meter_gas_consumption_2")
    assert gas_consumption is None

    # check if water usage mbus3 is parsed correctly
    water_consumption = hass.states.get("sensor.water_meter_water_consumption")
    assert water_consumption
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


async def test_belgian_meter_low(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Test if Belgian meter is correctly parsed."""
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5B",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        ELECTRICITY_ACTIVE_TARIFF,
        CosemObject((0, 0), [{"value": "0002", "unit": ""}]),
        "ELECTRICITY_ACTIVE_TARIFF",
    )

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
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5S",
        "serial_id": None,
        "serial_id_gas": None,
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        ELECTRICITY_IMPORTED_TOTAL,
        CosemObject(
            (0, 0),
            [{"value": Decimal("123.456"), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
        "ELECTRICITY_IMPORTED_TOTAL",
    )
    telegram.add(
        ELECTRICITY_EXPORTED_TOTAL,
        CosemObject(
            (0, 0),
            [{"value": Decimal("654.321"), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
        "ELECTRICITY_EXPORTED_TOTAL",
    )

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
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "Q3D",
        "serial_id": None,
        "serial_id_gas": None,
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        ELECTRICITY_IMPORTED_TOTAL,
        CosemObject(
            (0, 0),
            [{"value": Decimal("54184.6316"), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
        "ELECTRICITY_IMPORTED_TOTAL",
    )
    telegram.add(
        ELECTRICITY_EXPORTED_TOTAL,
        CosemObject(
            (0, 0),
            [{"value": Decimal("19981.1069"), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
        "ELECTRICITY_EXPORTED_TOTAL",
    )

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
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

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

    # Legacy host/port entries are combined into a socket URL in memory and
    # opened with the keep-alive watchdog; the stored entry is left untouched so
    # a downgrade keeps working.
    assert mock_entry.data["host"] == "localhost"
    assert connection_factory.call_args_list[0][0][0] == "socket://localhost:1234"
    assert connection_factory.call_args_list[0][1]["keep_alive_interval"] == 60


async def test_rfxtrx_tcp(
    hass: HomeAssistant,
    rfxtrx_dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """If proper config provided RFXtrx TCP connection should be made."""
    (connection_factory, _transport, _protocol) = rfxtrx_dsmr_connection_fixture

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

    # Legacy host/port entries keep using the TCP reader (with keep-alive); the
    # stored entry is left untouched so a downgrade keeps working.
    assert mock_entry.data["host"] == "localhost"
    assert connection_factory.call_args_list[0][0][0] == "localhost"
    assert connection_factory.call_args_list[0][0][1] == 1234
    assert connection_factory.call_args_list[0][1]["keep_alive_interval"] == 60


async def test_tcp_socket_url(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """A socket:// port should be opened with the keep-alive watchdog."""
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "socket://localhost:1234",
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

    assert connection_factory.call_args_list[0][0][0] == "socket://localhost:1234"
    assert connection_factory.call_args_list[0][1]["keep_alive_interval"] == 60


async def test_serial_no_keep_alive(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """A local serial device should use the plain reader without keep-alive."""
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
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

    assert connection_factory.call_args_list[0][0][0] == "/dev/ttyUSB0"
    assert "keep_alive_interval" not in connection_factory.call_args_list[0][1]


@patch("homeassistant.components.dsmr.sensor.DEFAULT_RECONNECT_INTERVAL", 0)
async def test_connection_errors_retry(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Connection should be retried on error during setup."""
    (_connection_factory, transport, protocol) = dsmr_connection_fixture

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

    (connection_factory, _transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        CURRENT_ELECTRICITY_USAGE,
        CosemObject(
            (0, 0),
            [{"value": Decimal("35.0"), "unit": UnitOfPower.WATT}],
        ),
        "CURRENT_ELECTRICITY_USAGE",
    )
    telegram.add(
        ELECTRICITY_ACTIVE_TARIFF,
        CosemObject((0, 0), [{"value": "0001", "unit": ""}]),
        "ELECTRICITY_ACTIVE_TARIFF",
    )

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
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        GAS_METER_READING,
        MBusObject(
            (0, 0),
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal("123.456"), "unit": UnitOfEnergy.GIGA_JOULE},
            ],
        ),
        "GAS_METER_READING",
    )

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


async def test_heat_meter_mbus(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Test if heat meter reading is correctly parsed."""
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5",
        "serial_id": "1234",
        "serial_id_gas": None,
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        MBUS_DEVICE_TYPE,
        CosemObject((0, 1), [{"value": "004", "unit": ""}]),
        "MBUS_DEVICE_TYPE",
    )
    telegram.add(
        MBUS_METER_READING,
        MBusObject(
            (0, 1),
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal("745.695"), "unit": "GJ"},
            ],
        ),
        "MBUS_METER_READING",
    )

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    hass.loop.set_debug(True)
    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    # check if gas consumption is parsed correctly
    heat_consumption = hass.states.get("sensor.heat_meter_energy")
    assert heat_consumption.state == "745.695"
    assert (
        heat_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    )
    assert (
        heat_consumption.attributes.get("unit_of_measurement")
        == UnitOfEnergy.GIGA_JOULE
    )
    assert (
        heat_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )


async def test_heat_cool_meter_mbus(
    hass: HomeAssistant, dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock]
) -> None:
    """Test if heat/cool meter reading is correctly parsed."""
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5",
        "serial_id": "1234",
        "serial_id_gas": None,
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = Telegram()
    telegram.add(
        MBUS_DEVICE_TYPE,
        CosemObject((0, 1), [{"value": "012", "unit": ""}]),
        "MBUS_DEVICE_TYPE",
    )
    telegram.add(
        MBUS_METER_READING,
        MBusObject(
            (0, 1),
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal("745.695"), "unit": "GJ"},
            ],
        ),
        "MBUS_METER_READING",
    )

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    hass.loop.set_debug(True)
    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    # check if gas consumption is parsed correctly
    heat_consumption = hass.states.get("sensor.heat_meter_energy")
    assert heat_consumption.state == "745.695"
    assert (
        heat_consumption.attributes.get(ATTR_DEVICE_CLASS) == SensorDeviceClass.ENERGY
    )
    assert (
        heat_consumption.attributes.get("unit_of_measurement")
        == UnitOfEnergy.GIGA_JOULE
    )
    assert (
        heat_consumption.attributes.get(ATTR_STATE_CLASS)
        == SensorStateClass.TOTAL_INCREASING
    )


def test_all_obis_references_exists() -> None:
    """Verify that all attributes exist by name in database."""
    for sensor in SENSORS:
        assert hasattr(obis_references, sensor.obis_reference)

    for sensors in SENSORS_MBUS_DEVICE_TYPE.values():
        for sensor in sensors:
            assert hasattr(obis_references, sensor.obis_reference)


POWER_ENTITY_ID = "sensor.electricity_meter_power_consumption"
ENERGY_ENTITY_ID = "sensor.electricity_meter_energy_consumption_tarif_1"
CURRENT_ENTITY_ID = "sensor.electricity_meter_current_phase_l1"
VOLTAGE_ENTITY_ID = "sensor.electricity_meter_voltage_phase_l1"

UPDATE_INTERVAL = 30


def _create_power_and_energy_telegram(power: str, energy: str) -> Telegram:
    """Create a telegram with power and energy readings."""
    telegram = Telegram()
    telegram.add(
        CURRENT_ELECTRICITY_USAGE,
        CosemObject(
            (0, 0),
            [{"value": Decimal(power), "unit": UnitOfPower.WATT}],
        ),
        "CURRENT_ELECTRICITY_USAGE",
    )
    telegram.add(
        ELECTRICITY_USED_TARIFF_1,
        CosemObject(
            (0, 0),
            [{"value": Decimal(energy), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
        "ELECTRICITY_USED_TARIFF_1",
    )
    return telegram


def _create_current_and_voltage_telegram(current: str, voltage: str) -> Telegram:
    """Create a telegram with a current and a voltage reading.

    Both are fluctuating measurements that are averaged over the update interval.
    """
    telegram = Telegram()
    telegram.add(
        INSTANTANEOUS_CURRENT_L1,
        CosemObject(
            (0, 0),
            [{"value": Decimal(current), "unit": UnitOfElectricCurrent.AMPERE}],
        ),
        "INSTANTANEOUS_CURRENT_L1",
    )
    telegram.add(
        INSTANTANEOUS_VOLTAGE_L1,
        CosemObject(
            (0, 0),
            [{"value": Decimal(voltage), "unit": UnitOfElectricPotential.VOLT}],
        ),
        "INSTANTANEOUS_VOLTAGE_L1",
    )
    return telegram


def _create_energy_only_telegram(energy: str) -> Telegram:
    """Create a telegram with an energy reading but no power reading.

    Used to exercise an averaged sensor (power) whose object is absent from the
    telegrams arriving during an interval.
    """
    telegram = Telegram()
    telegram.add(
        ELECTRICITY_USED_TARIFF_1,
        CosemObject(
            (0, 0),
            [{"value": Decimal(energy), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
        "ELECTRICITY_USED_TARIFF_1",
    )
    return telegram


def _create_power_only_telegram(power: str) -> Telegram:
    """Create a telegram with a power reading but no energy reading.

    Used to exercise a non-averaged sensor (energy) whose object is absent from
    a telegram arriving later in the interval.
    """
    telegram = Telegram()
    telegram.add(
        CURRENT_ELECTRICITY_USAGE,
        CosemObject(
            (0, 0),
            [{"value": Decimal(power), "unit": UnitOfPower.WATT}],
        ),
        "CURRENT_ELECTRICITY_USAGE",
    )
    return telegram


async def _setup_dsmr_for_averaging(
    hass: HomeAssistant,
    connection_factory: MagicMock,
    time_between_update: int,
) -> Callable[[Telegram | None], None]:
    """Set up a DSMR config entry and return the telegram push callback.

    The connection fixture keeps the mocked connection open (``wait_closed``
    blocks until fixture teardown), so the background reconnect loop does not
    push empty telegrams that would reset the values accumulated for averaging
    while the test is running.
    """
    mock_entry = MockConfigEntry(
        domain="dsmr",
        unique_id="/dev/ttyUSB0",
        data={
            "port": "/dev/ttyUSB0",
            "dsmr_version": "2.2",
            "serial_id": "1234",
            "serial_id_gas": "5678",
        },
        options={"time_between_update": time_between_update},
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    # For a serial connection the telegram callback is the third argument.
    return connection_factory.call_args_list[0][0][2]


async def _advance_to_next_update(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Advance past the update interval so the timer publishes the values."""
    freezer.tick(datetime.timedelta(seconds=UPDATE_INTERVAL + 1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_power_readings_are_averaged_over_the_update_interval(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test that power readings are averaged over the configured interval."""
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    telegram_callback = await _setup_dsmr_for_averaging(
        hass, connection_factory, time_between_update=UPDATE_INTERVAL
    )

    # First telegram creates the entities and sets the initial value.
    telegram_callback(_create_power_and_energy_telegram("1.0", "100.0"))
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "1.0"

    # More telegrams arrive within the same interval. They are accumulated but
    # not published until the timer fires, so the reported state does not change.
    telegram_callback(_create_power_and_energy_telegram("2.0", "100.0"))
    await hass.async_block_till_done()
    telegram_callback(_create_power_and_energy_telegram("4.0", "100.0"))
    await hass.async_block_till_done()
    telegram_callback(_create_power_and_energy_telegram("6.0", "100.0"))
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "1.0"

    # When the interval elapses the timer publishes the mean of the values
    # accumulated during the window: mean(2, 4, 6) == 4.
    await _advance_to_next_update(hass, freezer)
    assert hass.states.get(POWER_ENTITY_ID).state == "4.0"

    # A new interval starts with an empty accumulator: values from the previous
    # window are not carried over. mean(8, 10, 12) == 10.
    telegram_callback(_create_power_and_energy_telegram("8.0", "100.0"))
    await hass.async_block_till_done()
    telegram_callback(_create_power_and_energy_telegram("10.0", "100.0"))
    await hass.async_block_till_done()
    telegram_callback(_create_power_and_energy_telegram("12.0", "100.0"))
    await hass.async_block_till_done()
    await _advance_to_next_update(hass, freezer)
    assert hass.states.get(POWER_ENTITY_ID).state == "10.0"


async def test_averaged_sensor_unavailable_without_readings_in_interval(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test that an averaged sensor with no reading for an interval is unavailable.

    A whole interval can pass without any reading either because no telegram
    arrives or because the telegrams that do arrive omit the averaged object.
    In both cases keeping the previous interval's value would be misleading, so
    the sensor becomes unavailable; it recovers once a reading returns. A
    non-averaged sensor present in the same telegrams keeps reporting throughout.
    """
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    telegram_callback = await _setup_dsmr_for_averaging(
        hass, connection_factory, time_between_update=UPDATE_INTERVAL
    )

    # Establish and publish an average for the first window: mean(2, 4, 6) == 4.
    telegram_callback(_create_power_and_energy_telegram("1.0", "100.0"))
    await hass.async_block_till_done()
    telegram_callback(_create_power_and_energy_telegram("2.0", "100.0"))
    await hass.async_block_till_done()
    telegram_callback(_create_power_and_energy_telegram("4.0", "100.0"))
    await hass.async_block_till_done()
    telegram_callback(_create_power_and_energy_telegram("6.0", "100.0"))
    await hass.async_block_till_done()
    await _advance_to_next_update(hass, freezer)
    assert hass.states.get(POWER_ENTITY_ID).state == "4.0"

    # No telegram arrives during the next interval: there is no reading to
    # report, so the sensor is unavailable instead of holding the previous value.
    await _advance_to_next_update(hass, freezer)
    assert hass.states.get(POWER_ENTITY_ID).state == STATE_UNAVAILABLE

    # Telegrams keep arriving but omit the power object for the whole interval:
    # the averaged sensor stays unavailable, while the non-averaged energy sensor
    # carried by the same telegrams keeps reporting its latest value.
    telegram_callback(_create_energy_only_telegram("110.0"))
    await hass.async_block_till_done()
    telegram_callback(_create_energy_only_telegram("120.0"))
    await hass.async_block_till_done()
    await _advance_to_next_update(hass, freezer)
    assert hass.states.get(POWER_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(ENERGY_ENTITY_ID).state == "120.0"

    # A power reading restores the sensor: mean(8, 10) == 9.
    telegram_callback(_create_power_and_energy_telegram("8.0", "100.0"))
    await hass.async_block_till_done()
    telegram_callback(_create_power_and_energy_telegram("10.0", "100.0"))
    await hass.async_block_till_done()
    await _advance_to_next_update(hass, freezer)
    assert hass.states.get(POWER_ENTITY_ID).state == "9.0"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_current_and_voltage_readings_are_averaged(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test that current and voltage readings are averaged like power."""
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    telegram_callback = await _setup_dsmr_for_averaging(
        hass, connection_factory, time_between_update=UPDATE_INTERVAL
    )

    telegram_callback(_create_current_and_voltage_telegram("1.0", "230.0"))
    await hass.async_block_till_done()
    assert hass.states.get(CURRENT_ENTITY_ID).state == "1.0"
    assert hass.states.get(VOLTAGE_ENTITY_ID).state == "230.0"

    telegram_callback(_create_current_and_voltage_telegram("2.0", "231.0"))
    await hass.async_block_till_done()
    telegram_callback(_create_current_and_voltage_telegram("4.0", "233.0"))
    await hass.async_block_till_done()
    telegram_callback(_create_current_and_voltage_telegram("6.0", "235.0"))
    await hass.async_block_till_done()

    # mean(2, 4, 6) == 4 amps; mean(231, 233, 235) == 233 volts.
    await _advance_to_next_update(hass, freezer)
    assert hass.states.get(CURRENT_ENTITY_ID).state == "4.0"
    assert hass.states.get(VOLTAGE_ENTITY_ID).state == "233.0"


async def test_averaged_power_value_is_rounded_to_default_precision(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test that the averaged power value is rounded to the default precision."""
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    telegram_callback = await _setup_dsmr_for_averaging(
        hass, connection_factory, time_between_update=UPDATE_INTERVAL
    )

    telegram_callback(_create_power_and_energy_telegram("1.0", "100.0"))
    await hass.async_block_till_done()

    # Accumulate values whose mean is not exactly representable:
    # mean(1, 2, 2) == 1.6666... which is rounded to 3 decimals -> 1.667.
    telegram_callback(_create_power_and_energy_telegram("1.0", "100.0"))
    await hass.async_block_till_done()
    telegram_callback(_create_power_and_energy_telegram("2.0", "100.0"))
    await hass.async_block_till_done()
    telegram_callback(_create_power_and_energy_telegram("2.0", "100.0"))
    await hass.async_block_till_done()

    await _advance_to_next_update(hass, freezer)
    assert hass.states.get(POWER_ENTITY_ID).state == "1.667"


async def test_non_power_readings_are_not_averaged(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test that non-averaged readings keep their last value instead of averaging."""
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    telegram_callback = await _setup_dsmr_for_averaging(
        hass, connection_factory, time_between_update=UPDATE_INTERVAL
    )

    telegram_callback(_create_power_and_energy_telegram("1.0", "10.0"))
    await hass.async_block_till_done()
    assert hass.states.get(ENERGY_ENTITY_ID).state == "10.0"

    # Several telegrams arrive within the interval. The energy reading is not
    # accumulated and the state is not published until the interval elapses.
    telegram_callback(_create_power_and_energy_telegram("2.0", "20.0"))
    await hass.async_block_till_done()
    telegram_callback(_create_power_and_energy_telegram("4.0", "30.0"))
    await hass.async_block_till_done()
    telegram_callback(_create_power_and_energy_telegram("6.0", "40.0"))
    await hass.async_block_till_done()
    assert hass.states.get(ENERGY_ENTITY_ID).state == "10.0"

    # After the interval the energy sensor reports the last received value (40),
    # not the mean of the values seen during the window.
    await _advance_to_next_update(hass, freezer)
    assert hass.states.get(ENERGY_ENTITY_ID).state == "40.0"

    # The power sensor on the very same telegrams *is* averaged: mean(2, 4, 6).
    assert hass.states.get(POWER_ENTITY_ID).state == "4.0"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_non_averaged_value_survives_later_partial_telegram(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test a non-averaged reading is kept when a later telegram omits its object.

    A non-averaged value that appears earlier in the interval must be published
    at the timer tick even if the last telegram of the interval is a partial one
    that omits the object, instead of falling back to the previous value.
    """
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    telegram_callback = await _setup_dsmr_for_averaging(
        hass, connection_factory, time_between_update=UPDATE_INTERVAL
    )

    # First telegram creates the entities and sets the initial energy value.
    telegram_callback(_create_power_and_energy_telegram("1.0", "10.0"))
    await hass.async_block_till_done()
    assert hass.states.get(ENERGY_ENTITY_ID).state == "10.0"

    # A new energy reading (50) arrives within the interval, followed by a
    # partial telegram that omits the energy object before the timer fires.
    telegram_callback(_create_power_and_energy_telegram("2.0", "50.0"))
    await hass.async_block_till_done()
    telegram_callback(_create_power_only_telegram("4.0"))
    await hass.async_block_till_done()

    # The latest energy value seen during the interval (50) is published, not
    # the stale 10 from before: the partial telegram must not drop the reading.
    await _advance_to_next_update(hass, freezer)
    assert hass.states.get(ENERGY_ENTITY_ID).state == "50.0"


async def test_force_update_sensor_not_rewritten_without_new_reading(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test a force_update sensor is only rewritten after a new reading.

    The EON HU tariff totals use force_update, so rewriting their cached value
    on every timer tick would fire state-change events every interval even when
    telegrams (or their objects) stop arriving. Ticks without a new reading must
    not rewrite the state; a fresh reading (even an unchanged one) must.
    """
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    mock_entry = MockConfigEntry(
        domain="dsmr",
        unique_id="/dev/ttyUSB0",
        data={
            "port": "/dev/ttyUSB0",
            "dsmr_version": "5EONHU",
            "serial_id": "1234",
        },
        options={"time_between_update": UPDATE_INTERVAL},
    )
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    telegram_callback = connection_factory.call_args_list[0][0][2]

    tariff_telegram = Telegram()
    tariff_telegram.add(
        ELECTRICITY_USED_TARIFF_3,
        CosemObject(
            (0, 0),
            [{"value": Decimal("100.0"), "unit": UnitOfEnergy.KILO_WATT_HOUR}],
        ),
        "ELECTRICITY_USED_TARIFF_3",
    )
    telegram_callback(tariff_telegram)
    await hass.async_block_till_done()

    tariff_entity_id = "sensor.electricity_meter_energy_consumption_tarif_3"
    state = hass.states.get(tariff_entity_id)
    assert state.state == "100.0"
    last_updated = state.last_updated

    # Ticks without any telegram must not rewrite the cached value: with
    # force_update every rewrite would fire a state-change event.
    await _advance_to_next_update(hass, freezer)
    await _advance_to_next_update(hass, freezer)
    state = hass.states.get(tariff_entity_id)
    assert state.state == "100.0"
    assert state.last_updated == last_updated

    # Telegrams resume but omit the tariff object: still no rewrite.
    telegram_callback(_create_power_only_telegram("5.0"))
    await hass.async_block_till_done()
    await _advance_to_next_update(hass, freezer)
    state = hass.states.get(tariff_entity_id)
    assert state.last_updated == last_updated

    # A fresh reading with the same value is published again (force_update).
    telegram_callback(tariff_telegram)
    await hass.async_block_till_done()
    await _advance_to_next_update(hass, freezer)
    state = hass.states.get(tariff_entity_id)
    assert state.state == "100.0"
    assert state.last_updated > last_updated


async def test_no_averaging_when_update_interval_is_zero(
    hass: HomeAssistant,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test that with a zero interval every telegram is published unchanged."""
    (connection_factory, _transport, _protocol) = dsmr_connection_fixture

    telegram_callback = await _setup_dsmr_for_averaging(
        hass, connection_factory, time_between_update=0
    )

    telegram_callback(_create_power_and_energy_telegram("5.0", "100.0"))
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "5.0"

    # Without an averaging window each telegram is published immediately with
    # its own value (15), not averaged with the previous one (which would be 10).
    telegram_callback(_create_power_and_energy_telegram("15.0", "100.0"))
    await hass.async_block_till_done()
    assert hass.states.get(POWER_ENTITY_ID).state == "15.0"
