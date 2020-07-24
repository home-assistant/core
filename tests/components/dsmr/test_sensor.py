"""Test for DSMR components.

Tests setup of the DSMR component and ensure incoming telegrams cause
Entity to be updated with new values.

"""

import asyncio
import datetime
from decimal import Decimal
from itertools import chain, repeat

import pytest

from homeassistant.components.dsmr.const import (
    CONF_DSMR_VERSION,
    CONF_POWER_WATT,
    CONF_PRECISION,
    CONF_RECONNECT_INTERVAL,
    CONF_SERIAL_ID,
    CONF_SERIAL_ID_GAS,
    DOMAIN,
)
from homeassistant.components.dsmr.sensor import DerivativeDSMREntity, DSMREntity
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    ENERGY_KILO_WATT_HOUR,
    POWER_KILO_WATT,
    POWER_WATT,
    TIME_HOURS,
    VOLUME_CUBIC_METERS,
)
from homeassistant.helpers import entity_registry

import tests.async_mock
from tests.async_mock import DEFAULT, Mock
from tests.common import MockConfigEntry

TEST_HOST = "localhost"
TEST_PORT = "1234"
TEST_USB_PATH = "/dev/ttyUSB0"
TEST_SERIALNUMBER = "12345678"
TEST_SERIALNUMBER_GAS = "123456789"
TEST_PRECISION = 3
TEST_RECONNECT_INTERVAL = 30
TEST_UNIQUE_ID = f"{DOMAIN}-{TEST_SERIALNUMBER}"
TEST_DSMR_VERSION = "2.2"
TEST_POWER_WATT = False


@pytest.fixture
def mock_connection_factory(monkeypatch):
    """Mock the create functions for serial and TCP Asyncio connections."""
    from dsmr_parser.clients.protocol import DSMRProtocol

    transport = tests.async_mock.Mock(spec=asyncio.Transport)
    protocol = tests.async_mock.Mock(spec=DSMRProtocol)

    async def connection_factory(*args, **kwargs):
        """Return mocked out Asyncio classes."""
        return (transport, protocol)

    connection_factory = Mock(wraps=connection_factory)

    # apply the mock to both connection factories
    monkeypatch.setattr(
        "homeassistant.components.dsmr.sensor.create_dsmr_reader", connection_factory
    )
    monkeypatch.setattr(
        "homeassistant.components.dsmr.sensor.create_tcp_dsmr_reader",
        connection_factory,
    )

    return connection_factory, transport, protocol


async def test_entity():
    """Test the basic property of the entity."""
    config = {"platform": DOMAIN}

    entity = DSMREntity("test", "1234", "test_device", "5678", "1.0.0", config)

    assert entity.force_update
    assert not entity.should_poll
    assert entity.unique_id == "1234_test"

    device_info = entity.device_info

    assert device_info
    assert device_info["identifiers"] == {(DOMAIN, "5678")}
    assert device_info["name"] == "test_device"


async def test_default_setup(hass, mock_connection_factory):
    """Test the default setup."""
    (connection_factory, transport, protocol) = mock_connection_factory

    from dsmr_parser.obis_references import (
        ELECTRICITY_ACTIVE_TARIFF,
        ELECTRICITY_USED_TARIFF_1,
        GAS_METER_READING,
        CURRENT_ELECTRICITY_USAGE,
        CURRENT_ELECTRICITY_DELIVERY,
    )
    from dsmr_parser.objects import CosemObject, MBusObject

    entry_data = {
        CONF_PORT: TEST_USB_PATH,
        CONF_DSMR_VERSION: TEST_DSMR_VERSION,
        CONF_SERIAL_ID: TEST_SERIALNUMBER,
        CONF_SERIAL_ID_GAS: TEST_SERIALNUMBER_GAS,
        CONF_PRECISION: 4,
        CONF_POWER_WATT: TEST_POWER_WATT,
    }

    telegram = {
        ELECTRICITY_USED_TARIFF_1: CosemObject(
            [{"value": Decimal("0.0"), "unit": ENERGY_KILO_WATT_HOUR}]
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject([{"value": "0001", "unit": ""}]),
        GAS_METER_READING: MBusObject(
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(745.695), "unit": VOLUME_CUBIC_METERS},
            ]
        ),
        CURRENT_ELECTRICITY_USAGE: CosemObject(
            [{"value": Decimal("2343.2"), "unit": POWER_WATT}]
        ),
        CURRENT_ELECTRICITY_DELIVERY: CosemObject(
            [{"value": Decimal("2.3432"), "unit": POWER_KILO_WATT}]
        ),
    }

    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=TEST_UNIQUE_ID, data=entry_data
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

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
    energy_consumption = hass.states.get("sensor.energy_consumption_tarif_1")
    assert energy_consumption.state == "0.0"
    assert (
        energy_consumption.attributes.get("unit_of_measurement")
        == ENERGY_KILO_WATT_HOUR
    )

    # check if power units are untouched
    power_consumption = hass.states.get("sensor.power_consumption")
    assert power_consumption.state == "2343.2"
    assert power_consumption.attributes.get("unit_of_measurement") == POWER_WATT

    power_production = hass.states.get("sensor.power_production")
    assert power_production.state == "2.3432"
    assert power_production.attributes.get("unit_of_measurement") == POWER_KILO_WATT

    # tariff should be translated in human readable and have no unit
    power_tariff = hass.states.get("sensor.power_tariff")
    assert power_tariff.state == "low"
    assert power_tariff.attributes.get("unit_of_measurement") == ""

    # check if gas consumption is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_consumption")
    assert gas_consumption.state == "745.695"
    assert gas_consumption.attributes.get("unit_of_measurement") == VOLUME_CUBIC_METERS


async def test_power_in_watt(hass, mock_connection_factory):
    """Test the setup with power in watt."""
    (connection_factory, transport, protocol) = mock_connection_factory

    from dsmr_parser.obis_references import (
        ELECTRICITY_ACTIVE_TARIFF,
        ELECTRICITY_USED_TARIFF_1,
        GAS_METER_READING,
        CURRENT_ELECTRICITY_USAGE,
        CURRENT_ELECTRICITY_DELIVERY,
    )
    from dsmr_parser.objects import CosemObject, MBusObject

    entry_data = {
        CONF_PORT: TEST_USB_PATH,
        CONF_DSMR_VERSION: TEST_DSMR_VERSION,
        CONF_SERIAL_ID: TEST_SERIALNUMBER,
        CONF_SERIAL_ID_GAS: TEST_SERIALNUMBER_GAS,
        CONF_PRECISION: 4,
        CONF_POWER_WATT: True,
    }

    telegram = {
        ELECTRICITY_USED_TARIFF_1: CosemObject(
            [{"value": Decimal("0.0"), "unit": ENERGY_KILO_WATT_HOUR}]
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject([{"value": "0001", "unit": ""}]),
        GAS_METER_READING: MBusObject(
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(745.695), "unit": VOLUME_CUBIC_METERS},
            ]
        ),
        CURRENT_ELECTRICITY_USAGE: CosemObject(
            [{"value": Decimal("2343.2"), "unit": POWER_WATT}]
        ),
        CURRENT_ELECTRICITY_DELIVERY: CosemObject(
            [{"value": Decimal("2.3432"), "unit": POWER_KILO_WATT}]
        ),
    }

    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=TEST_UNIQUE_ID, data=entry_data
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

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
    energy_consumption = hass.states.get("sensor.energy_consumption_tarif_1")
    assert energy_consumption.state == "0.0"
    assert (
        energy_consumption.attributes.get("unit_of_measurement")
        == ENERGY_KILO_WATT_HOUR
    )

    # check if power units are untouched
    power_consumption = hass.states.get("sensor.power_consumption")
    assert power_consumption.state == "2343.2"
    assert power_consumption.attributes.get("unit_of_measurement") == POWER_WATT

    power_production = hass.states.get("sensor.power_production")
    assert power_production.state == "2343.2"
    assert power_production.attributes.get("unit_of_measurement") == POWER_WATT

    # tariff should be translated in human readable and have no unit
    power_tariff = hass.states.get("sensor.power_tariff")
    assert power_tariff.state == "low"
    assert power_tariff.attributes.get("unit_of_measurement") == ""

    # check if gas consumption is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_consumption")
    assert gas_consumption.state == "745.695"
    assert gas_consumption.attributes.get("unit_of_measurement") == VOLUME_CUBIC_METERS

    registry = await entity_registry.async_get_registry(hass)
    entry = registry.async_get("sensor.power_consumption")

    assert entry
    assert entry.unique_id


async def test_derivative():
    """Test calculation of derivative value."""
    from dsmr_parser.objects import MBusObject

    config = {"platform": DOMAIN}

    entity = DerivativeDSMREntity("test", "1", "", "", "1.0.0", config)
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

    assert entity.unit_of_measurement == f"{VOLUME_CUBIC_METERS}/{TIME_HOURS}"


async def test_v4_meter(hass, mock_connection_factory):
    """Test if v4 meter is correctly parsed."""
    (connection_factory, transport, protocol) = mock_connection_factory

    from dsmr_parser.obis_references import (
        HOURLY_GAS_METER_READING,
        ELECTRICITY_ACTIVE_TARIFF,
    )
    from dsmr_parser.objects import CosemObject, MBusObject

    entry_data = {
        CONF_PORT: TEST_USB_PATH,
        CONF_DSMR_VERSION: "4",
        CONF_SERIAL_ID: TEST_SERIALNUMBER,
        CONF_SERIAL_ID_GAS: TEST_SERIALNUMBER_GAS,
        CONF_PRECISION: TEST_PRECISION,
        CONF_RECONNECT_INTERVAL: TEST_RECONNECT_INTERVAL,
        CONF_POWER_WATT: TEST_POWER_WATT,
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
        domain=DOMAIN, unique_id=TEST_UNIQUE_ID, data=entry_data
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

    # # check if gas consumption is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_consumption")
    assert gas_consumption.state == "745.695"
    assert gas_consumption.attributes.get("unit_of_measurement") == VOLUME_CUBIC_METERS


async def test_v5_meter(hass, mock_connection_factory):
    """Test if v5 meter is correctly parsed."""
    (connection_factory, transport, protocol) = mock_connection_factory

    from dsmr_parser.obis_references import (
        HOURLY_GAS_METER_READING,
        ELECTRICITY_ACTIVE_TARIFF,
    )
    from dsmr_parser.objects import CosemObject, MBusObject

    entry_data = {
        CONF_PORT: TEST_USB_PATH,
        CONF_DSMR_VERSION: "5",
        CONF_SERIAL_ID: TEST_SERIALNUMBER,
        CONF_SERIAL_ID_GAS: TEST_SERIALNUMBER_GAS,
        CONF_PRECISION: TEST_PRECISION,
        CONF_RECONNECT_INTERVAL: TEST_RECONNECT_INTERVAL,
        CONF_POWER_WATT: TEST_POWER_WATT,
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
        domain=DOMAIN, unique_id=TEST_UNIQUE_ID, data=entry_data
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


async def test_belgian_meter(hass, mock_connection_factory):
    """Test if Belgian meter is correctly parsed."""
    (connection_factory, transport, protocol) = mock_connection_factory

    from dsmr_parser.obis_references import (
        BELGIUM_HOURLY_GAS_METER_READING,
        ELECTRICITY_ACTIVE_TARIFF,
    )
    from dsmr_parser.objects import CosemObject, MBusObject

    entry_data = {
        CONF_PORT: TEST_USB_PATH,
        CONF_DSMR_VERSION: "5B",
        CONF_SERIAL_ID: TEST_SERIALNUMBER,
        CONF_SERIAL_ID_GAS: TEST_SERIALNUMBER_GAS,
        CONF_PRECISION: TEST_PRECISION,
        CONF_RECONNECT_INTERVAL: TEST_RECONNECT_INTERVAL,
        CONF_POWER_WATT: TEST_POWER_WATT,
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
        domain=DOMAIN, unique_id=TEST_UNIQUE_ID, data=entry_data
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


async def test_belgian_meter_low(hass, mock_connection_factory):
    """Test if Belgian meter is correctly parsed."""
    (connection_factory, transport, protocol) = mock_connection_factory

    from dsmr_parser.obis_references import ELECTRICITY_ACTIVE_TARIFF
    from dsmr_parser.objects import CosemObject

    entry_data = {
        CONF_PORT: TEST_USB_PATH,
        CONF_DSMR_VERSION: "5B",
        CONF_SERIAL_ID: TEST_SERIALNUMBER,
        CONF_SERIAL_ID_GAS: TEST_SERIALNUMBER_GAS,
        CONF_PRECISION: TEST_PRECISION,
        CONF_RECONNECT_INTERVAL: TEST_RECONNECT_INTERVAL,
        CONF_POWER_WATT: TEST_POWER_WATT,
    }

    telegram = {ELECTRICITY_ACTIVE_TARIFF: CosemObject([{"value": "0002", "unit": ""}])}

    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=TEST_UNIQUE_ID, data=entry_data
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


async def test_tcp(hass, mock_connection_factory):
    """If proper config provided TCP connection should be made."""
    (connection_factory, transport, protocol) = mock_connection_factory

    entry_data = {
        CONF_HOST: TEST_HOST,
        CONF_PORT: TEST_PORT,
        CONF_DSMR_VERSION: TEST_DSMR_VERSION,
        CONF_SERIAL_ID: TEST_SERIALNUMBER,
        CONF_SERIAL_ID_GAS: TEST_SERIALNUMBER_GAS,
        CONF_PRECISION: TEST_PRECISION,
        CONF_RECONNECT_INTERVAL: TEST_RECONNECT_INTERVAL,
        CONF_POWER_WATT: TEST_POWER_WATT,
    }

    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=TEST_UNIQUE_ID, data=entry_data
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert connection_factory.call_args_list[0][0][0] == "localhost"
    assert connection_factory.call_args_list[0][0][1] == "1234"


async def test_connection_errors_retry(hass, monkeypatch, mock_connection_factory):
    """Connection should be retried on error during setup."""
    (connection_factory, transport, protocol) = mock_connection_factory

    entry_data = {
        CONF_PORT: TEST_USB_PATH,
        CONF_DSMR_VERSION: TEST_DSMR_VERSION,
        CONF_SERIAL_ID: TEST_SERIALNUMBER,
        CONF_SERIAL_ID_GAS: TEST_SERIALNUMBER_GAS,
        CONF_PRECISION: TEST_PRECISION,
        CONF_RECONNECT_INTERVAL: 0,
        CONF_POWER_WATT: TEST_POWER_WATT,
    }

    # override the mock to have it fail the first time and succeed after
    first_fail_connection_factory = tests.async_mock.AsyncMock(
        return_value=(transport, protocol),
        side_effect=chain([TimeoutError], repeat(DEFAULT)),
    )

    monkeypatch.setattr(
        "homeassistant.components.dsmr.sensor.create_dsmr_reader",
        first_fail_connection_factory,
    )

    mock_entry = MockConfigEntry(
        domain="dsmr", unique_id=TEST_UNIQUE_ID, data=entry_data
    )

    mock_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_entry.entry_id)

    # wait for sleep to resolve
    await hass.async_block_till_done()
    assert first_fail_connection_factory.call_count >= 2, "connecting not retried"


async def test_reconnect(hass, monkeypatch, mock_connection_factory):
    """If transport disconnects, the connection should be retried."""
    (connection_factory, transport, protocol) = mock_connection_factory

    entry_data = {
        CONF_PORT: TEST_USB_PATH,
        CONF_DSMR_VERSION: TEST_DSMR_VERSION,
        CONF_SERIAL_ID: TEST_SERIALNUMBER,
        CONF_SERIAL_ID_GAS: TEST_SERIALNUMBER_GAS,
        CONF_PRECISION: TEST_PRECISION,
        CONF_RECONNECT_INTERVAL: 0,
        CONF_POWER_WATT: TEST_POWER_WATT,
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
        domain="dsmr", unique_id=TEST_UNIQUE_ID, data=entry_data
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

    await hass.async_block_till_done()
