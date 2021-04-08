"""Test for DSMR components.

Tests setup of the DSMR component and ensure incoming telegrams cause
Entity to be updated with new values.

"""

import asyncio
import datetime
from decimal import Decimal
from itertools import chain, repeat
from unittest.mock import DEFAULT, MagicMock

from homeassistant.components.dsmr.const import DOMAIN
from homeassistant.components.dsmr.sensor import DerivativeDSMREntity
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import (
    ENERGY_KILO_WATT_HOUR,
    VOLUME_CUBIC_METERS,
    VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, patch


async def test_setup_platform(hass, dsmr_connection_fixture):
    """Test setup of platform."""
    async_add_entities = MagicMock()

    entry_data = {
        "platform": DOMAIN,
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "precision": 4,
        "reconnect_interval": 30,
    }

    serial_data = {"serial_id": "1234", "serial_id_gas": "5678"}

    with patch(
        "homeassistant.components.dsmr.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.dsmr.config_flow._validate_dsmr_connection",
        return_value=serial_data,
    ):
        assert await async_setup_component(
            hass, SENSOR_DOMAIN, {SENSOR_DOMAIN: entry_data}
        )
        await hass.async_block_till_done()

    assert not async_add_entities.called

    # Check config entry
    conf_entries = hass.config_entries.async_entries(DOMAIN)

    assert len(conf_entries) == 1

    entry = conf_entries[0]

    assert entry.state == "loaded"
    assert entry.data == {**entry_data, **serial_data}


async def test_default_setup(hass, dsmr_connection_fixture):
    """Test the default setup."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    from dsmr_parser.obis_references import (
        CURRENT_ELECTRICITY_USAGE,
        ELECTRICITY_ACTIVE_TARIFF,
        GAS_METER_READING,
    )
    from dsmr_parser.objects import CosemObject, MBusObject

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "precision": 4,
        "reconnect_interval": 30,
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        CURRENT_ELECTRICITY_USAGE: CosemObject(
            [{"value": Decimal("0.0"), "unit": ENERGY_KILO_WATT_HOUR}]
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject([{"value": "0001", "unit": ""}]),
        GAS_METER_READING: MBusObject(
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(745.695), "unit": VOLUME_CUBIC_METERS},
            ]
        ),
    }

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)

    entry = registry.async_get("sensor.power_consumption")
    assert entry
    assert entry.unique_id == "1234_Power_Consumption"

    entry = registry.async_get("sensor.gas_consumption")
    assert entry
    assert entry.unique_id == "5678_Gas_Consumption"

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # make sure entities have been created and return 'unknown' state
    power_consumption = hass.states.get("sensor.power_consumption")
    assert power_consumption.state == "unknown"
    assert power_consumption.attributes.get("unit_of_measurement") is None

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to update
    await asyncio.sleep(0)

    # ensure entities have new state value after incoming telegram
    power_consumption = hass.states.get("sensor.power_consumption")
    assert power_consumption.state == "0.0"
    assert (
        power_consumption.attributes.get("unit_of_measurement") == ENERGY_KILO_WATT_HOUR
    )

    # tariff should be translated in human readable and have no unit
    power_tariff = hass.states.get("sensor.power_tariff")
    assert power_tariff.state == "low"
    assert power_tariff.attributes.get("unit_of_measurement") == ""

    # check if gas consumption is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_consumption")
    assert gas_consumption.state == "745.695"
    assert gas_consumption.attributes.get("unit_of_measurement") == VOLUME_CUBIC_METERS


async def test_setup_only_energy(hass, dsmr_connection_fixture):
    """Test the default setup."""
    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "precision": 4,
        "reconnect_interval": 30,
        "serial_id": "1234",
    }

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)

    entry = registry.async_get("sensor.power_consumption")
    assert entry
    assert entry.unique_id == "1234_Power_Consumption"

    entry = registry.async_get("sensor.gas_consumption")
    assert not entry


async def test_derivative():
    """Test calculation of derivative value."""
    from dsmr_parser.objects import MBusObject

    config = {"platform": "dsmr"}

    entity = DerivativeDSMREntity("test", "test_device", "5678", "1.0.0", config, False)
    await entity.async_update()

    assert entity.state is None, "initial state not unknown"

    entity.telegram = {
        "1.0.0": MBusObject(
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(745.695), "unit": VOLUME_CUBIC_METERS},
            ]
        )
    }
    await entity.async_update()

    assert entity.state is None, "state after first update should still be unknown"

    entity.telegram = {
        "1.0.0": MBusObject(
            [
                {"value": datetime.datetime.fromtimestamp(1551642543)},
                {"value": Decimal(745.698), "unit": VOLUME_CUBIC_METERS},
            ]
        )
    }
    await entity.async_update()

    assert (
        abs(entity.state - 0.033) < 0.00001
    ), "state should be hourly usage calculated from first and second update"

    assert entity.unit_of_measurement == VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR


async def test_v4_meter(hass, dsmr_connection_fixture):
    """Test if v4 meter is correctly parsed."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    from dsmr_parser.obis_references import (
        ELECTRICITY_ACTIVE_TARIFF,
        HOURLY_GAS_METER_READING,
    )
    from dsmr_parser.objects import CosemObject, MBusObject

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "4",
        "precision": 4,
        "reconnect_interval": 30,
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        HOURLY_GAS_METER_READING: MBusObject(
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(745.695), "unit": VOLUME_CUBIC_METERS},
            ]
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject([{"value": "0001", "unit": ""}]),
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

    # after receiving telegram entities need to have the chance to update
    await asyncio.sleep(0)

    # tariff should be translated in human readable and have no unit
    power_tariff = hass.states.get("sensor.power_tariff")
    assert power_tariff.state == "low"
    assert power_tariff.attributes.get("unit_of_measurement") == ""

    # check if gas consumption is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_consumption")
    assert gas_consumption.state == "745.695"
    assert gas_consumption.attributes.get("unit_of_measurement") == VOLUME_CUBIC_METERS


async def test_v5_meter(hass, dsmr_connection_fixture):
    """Test if v5 meter is correctly parsed."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    from dsmr_parser.obis_references import (
        ELECTRICITY_ACTIVE_TARIFF,
        HOURLY_GAS_METER_READING,
    )
    from dsmr_parser.objects import CosemObject, MBusObject

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5",
        "precision": 4,
        "reconnect_interval": 30,
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        HOURLY_GAS_METER_READING: MBusObject(
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(745.695), "unit": VOLUME_CUBIC_METERS},
            ]
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject([{"value": "0001", "unit": ""}]),
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

    # after receiving telegram entities need to have the chance to update
    await asyncio.sleep(0)

    # tariff should be translated in human readable and have no unit
    power_tariff = hass.states.get("sensor.power_tariff")
    assert power_tariff.state == "low"
    assert power_tariff.attributes.get("unit_of_measurement") == ""

    # check if gas consumption is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_consumption")
    assert gas_consumption.state == "745.695"
    assert gas_consumption.attributes.get("unit_of_measurement") == VOLUME_CUBIC_METERS


async def test_luxembourg_meter(hass, dsmr_connection_fixture):
    """Test if v5 meter is correctly parsed."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    from dsmr_parser.obis_references import (
        HOURLY_GAS_METER_READING,
        LUXEMBOURG_ELECTRICITY_DELIVERED_TARIFF_GLOBAL,
        LUXEMBOURG_ELECTRICITY_USED_TARIFF_GLOBAL,
    )
    from dsmr_parser.objects import CosemObject, MBusObject

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5L",
        "precision": 4,
        "reconnect_interval": 30,
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        HOURLY_GAS_METER_READING: MBusObject(
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(745.695), "unit": VOLUME_CUBIC_METERS},
            ]
        ),
        LUXEMBOURG_ELECTRICITY_USED_TARIFF_GLOBAL: CosemObject(
            [{"value": Decimal(123.456), "unit": ENERGY_KILO_WATT_HOUR}]
        ),
        LUXEMBOURG_ELECTRICITY_DELIVERED_TARIFF_GLOBAL: CosemObject(
            [{"value": Decimal(654.321), "unit": ENERGY_KILO_WATT_HOUR}]
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

    # after receiving telegram entities need to have the chance to update
    await asyncio.sleep(0)

    power_tariff = hass.states.get("sensor.energy_consumption_total")
    assert power_tariff.state == "123.456"
    assert power_tariff.attributes.get("unit_of_measurement") == ENERGY_KILO_WATT_HOUR

    power_tariff = hass.states.get("sensor.energy_production_total")
    assert power_tariff.state == "654.321"
    assert power_tariff.attributes.get("unit_of_measurement") == ENERGY_KILO_WATT_HOUR

    # check if gas consumption is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_consumption")
    assert gas_consumption.state == "745.695"
    assert gas_consumption.attributes.get("unit_of_measurement") == VOLUME_CUBIC_METERS


async def test_belgian_meter(hass, dsmr_connection_fixture):
    """Test if Belgian meter is correctly parsed."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    from dsmr_parser.obis_references import (
        BELGIUM_HOURLY_GAS_METER_READING,
        ELECTRICITY_ACTIVE_TARIFF,
    )
    from dsmr_parser.objects import CosemObject, MBusObject

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5B",
        "precision": 4,
        "reconnect_interval": 30,
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {
        BELGIUM_HOURLY_GAS_METER_READING: MBusObject(
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(745.695), "unit": VOLUME_CUBIC_METERS},
            ]
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject([{"value": "0001", "unit": ""}]),
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

    # after receiving telegram entities need to have the chance to update
    await asyncio.sleep(0)

    # tariff should be translated in human readable and have no unit
    power_tariff = hass.states.get("sensor.power_tariff")
    assert power_tariff.state == "normal"
    assert power_tariff.attributes.get("unit_of_measurement") == ""

    # check if gas consumption is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_consumption")
    assert gas_consumption.state == "745.695"
    assert gas_consumption.attributes.get("unit_of_measurement") == VOLUME_CUBIC_METERS


async def test_belgian_meter_low(hass, dsmr_connection_fixture):
    """Test if Belgian meter is correctly parsed."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    from dsmr_parser.obis_references import ELECTRICITY_ACTIVE_TARIFF
    from dsmr_parser.objects import CosemObject

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "5B",
        "precision": 4,
        "reconnect_interval": 30,
        "serial_id": "1234",
        "serial_id_gas": "5678",
    }
    entry_options = {
        "time_between_update": 0,
    }

    telegram = {ELECTRICITY_ACTIVE_TARIFF: CosemObject([{"value": "0002", "unit": ""}])}

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data, options=entry_options
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to update
    await asyncio.sleep(0)

    # tariff should be translated in human readable and have no unit
    power_tariff = hass.states.get("sensor.power_tariff")
    assert power_tariff.state == "low"
    assert power_tariff.attributes.get("unit_of_measurement") == ""


async def test_tcp(hass, dsmr_connection_fixture):
    """If proper config provided TCP connection should be made."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "host": "localhost",
        "port": "1234",
        "dsmr_version": "2.2",
        "precision": 4,
        "reconnect_interval": 30,
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


async def test_connection_errors_retry(hass, dsmr_connection_fixture):
    """Connection should be retried on error during setup."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "precision": 4,
        "reconnect_interval": 0,
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


async def test_reconnect(hass, dsmr_connection_fixture):
    """If transport disconnects, the connection should be retried."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    entry_data = {
        "port": "/dev/ttyUSB0",
        "dsmr_version": "2.2",
        "precision": 4,
        "reconnect_interval": 0,
        "serial_id": "1234",
        "serial_id_gas": "5678",
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
        domain="dsmr", unique_id="/dev/ttyUSB0", data=entry_data
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert connection_factory.call_count == 1

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

    assert mock_entry.state == "not_loaded"
