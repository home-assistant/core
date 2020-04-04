"""Test for DSMR components.

Tests setup of the DSMR component and ensure incoming telegrams cause
Entity to be updated with new values.

"""

import asyncio
import datetime
from decimal import Decimal
from itertools import chain, repeat
from unittest.mock import DEFAULT, Mock

import asynctest
import pytest

from homeassistant.bootstrap import async_setup_component
from homeassistant.components.dsmr.sensor import DerivativeDSMREntity
from homeassistant.const import TIME_HOURS, VOLUME_CUBIC_METERS

from tests.common import assert_setup_component


@pytest.fixture
def mock_connection_factory(monkeypatch):
    """Mock the create functions for serial and TCP Asyncio connections."""
    from dsmr_parser.clients.protocol import DSMRProtocol

    transport = asynctest.Mock(spec=asyncio.Transport)
    protocol = asynctest.Mock(spec=DSMRProtocol)

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


async def test_default_setup(hass, mock_connection_factory):
    """Test the default setup."""
    (connection_factory, transport, protocol) = mock_connection_factory

    from dsmr_parser.obis_references import (
        CURRENT_ELECTRICITY_USAGE,
        ELECTRICITY_ACTIVE_TARIFF,
        GAS_METER_READING,
    )
    from dsmr_parser.objects import CosemObject, MBusObject

    config = {"platform": "dsmr"}

    telegram = {
        CURRENT_ELECTRICITY_USAGE: CosemObject(
            [{"value": Decimal("0.0"), "unit": "kWh"}]
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject([{"value": "0001", "unit": ""}]),
        GAS_METER_READING: MBusObject(
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(745.695), "unit": VOLUME_CUBIC_METERS},
            ]
        ),
    }

    with assert_setup_component(1):
        await async_setup_component(hass, "sensor", {"sensor": config})

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
    assert power_consumption.attributes.get("unit_of_measurement") == "kWh"

    # tariff should be translated in human readable and have no unit
    power_tariff = hass.states.get("sensor.power_tariff")
    assert power_tariff.state == "low"
    assert power_tariff.attributes.get("unit_of_measurement") == ""

    # check if gas consumption is parsed correctly
    gas_consumption = hass.states.get("sensor.gas_consumption")
    assert gas_consumption.state == "745.695"
    assert gas_consumption.attributes.get("unit_of_measurement") == VOLUME_CUBIC_METERS


async def test_derivative():
    """Test calculation of derivative value."""
    from dsmr_parser.objects import MBusObject

    config = {"platform": "dsmr"}

    entity = DerivativeDSMREntity("test", "1.0.0", config)
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

    config = {"platform": "dsmr", "dsmr_version": "4"}

    telegram = {
        HOURLY_GAS_METER_READING: MBusObject(
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(745.695), "unit": VOLUME_CUBIC_METERS},
            ]
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject([{"value": "0001", "unit": ""}]),
    }

    with assert_setup_component(1):
        await async_setup_component(hass, "sensor", {"sensor": config})

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


async def test_v5_meter(hass, mock_connection_factory):
    """Test if v5 meter is correctly parsed."""
    (connection_factory, transport, protocol) = mock_connection_factory

    from dsmr_parser.obis_references import (
        HOURLY_GAS_METER_READING,
        ELECTRICITY_ACTIVE_TARIFF,
    )
    from dsmr_parser.objects import CosemObject, MBusObject

    config = {"platform": "dsmr", "dsmr_version": "5"}

    telegram = {
        HOURLY_GAS_METER_READING: MBusObject(
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(745.695), "unit": VOLUME_CUBIC_METERS},
            ]
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject([{"value": "0001", "unit": ""}]),
    }

    with assert_setup_component(1):
        await async_setup_component(hass, "sensor", {"sensor": config})

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

    config = {"platform": "dsmr", "dsmr_version": "5B"}

    telegram = {
        BELGIUM_HOURLY_GAS_METER_READING: MBusObject(
            [
                {"value": datetime.datetime.fromtimestamp(1551642213)},
                {"value": Decimal(745.695), "unit": VOLUME_CUBIC_METERS},
            ]
        ),
        ELECTRICITY_ACTIVE_TARIFF: CosemObject([{"value": "0001", "unit": ""}]),
    }

    with assert_setup_component(1):
        await async_setup_component(hass, "sensor", {"sensor": config})

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

    config = {"platform": "dsmr", "dsmr_version": "5B"}

    telegram = {ELECTRICITY_ACTIVE_TARIFF: CosemObject([{"value": "0002", "unit": ""}])}

    with assert_setup_component(1):
        await async_setup_component(hass, "sensor", {"sensor": config})

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

    config = {"platform": "dsmr", "host": "localhost", "port": 1234}

    with assert_setup_component(1):
        await async_setup_component(hass, "sensor", {"sensor": config})

    assert connection_factory.call_args_list[0][0][0] == "localhost"
    assert connection_factory.call_args_list[0][0][1] == "1234"


async def test_connection_errors_retry(hass, monkeypatch, mock_connection_factory):
    """Connection should be retried on error during setup."""
    (connection_factory, transport, protocol) = mock_connection_factory

    config = {"platform": "dsmr", "reconnect_interval": 0}

    # override the mock to have it fail the first time and succeed after
    first_fail_connection_factory = asynctest.CoroutineMock(
        return_value=(transport, protocol),
        side_effect=chain([TimeoutError], repeat(DEFAULT)),
    )

    monkeypatch.setattr(
        "homeassistant.components.dsmr.sensor.create_dsmr_reader",
        first_fail_connection_factory,
    )
    await async_setup_component(hass, "sensor", {"sensor": config})

    # wait for sleep to resolve
    await hass.async_block_till_done()
    assert first_fail_connection_factory.call_count >= 2, "connecting not retried"


async def test_reconnect(hass, monkeypatch, mock_connection_factory):
    """If transport disconnects, the connection should be retried."""
    (connection_factory, transport, protocol) = mock_connection_factory
    config = {"platform": "dsmr", "reconnect_interval": 0}

    # mock waiting coroutine while connection lasts
    closed = asyncio.Event()
    # Handshake so that `hass.async_block_till_done()` doesn't cycle forever
    closed2 = asyncio.Event()

    async def wait_closed():
        await closed.wait()
        closed2.set()

    protocol.wait_closed = wait_closed

    await async_setup_component(hass, "sensor", {"sensor": config})

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
