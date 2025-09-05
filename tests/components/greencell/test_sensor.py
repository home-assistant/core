"""Test cases for Greencell sensor components in Home Assistant."""

import asyncio
from types import SimpleNamespace

from greencell_client.mqtt_parser import MqttParser
import pytest

from homeassistant.components.greencell.sensor import (
    SENSOR_DESCRIPTIONS,
    Habu3PhaseSensor,
    HabuSingleSensor,
    async_setup_entry,
    async_setup_platform,
    setup_sensors,
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant

from .conftest import TEST_SERIAL_NUMBER, Dummy3PhaseData, DummyAccess, DummySingleData


def test_habu3phase_native_value_and_unique_id() -> None:
    """Test native value and unique ID for Habu3PhaseSensor."""

    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "current_l1")
    data = Dummy3PhaseData({"l1": 2000})
    access = DummyAccess()
    sensor = Habu3PhaseSensor(
        data,
        phase="l1",
        sensor_type="current_l1",
        serial_number=TEST_SERIAL_NUMBER,
        access=access,
        description=desc,
    )
    assert sensor.native_value == "2.000"
    data_null = Dummy3PhaseData({"l1": None})
    sensor_null = Habu3PhaseSensor(
        data_null,
        phase="l1",
        sensor_type="current_l1",
        serial_number=TEST_SERIAL_NUMBER,
        access=access,
        description=desc,
    )
    assert sensor_null.native_value == "0.000"
    assert sensor.unique_id == f"current_l1_sensor_l1_{TEST_SERIAL_NUMBER}"


def test_habu_single_native_value_and_unique_id() -> None:
    """Test native value and unique ID for HabuSingleSensor."""

    desc = next(d for d in SENSOR_DESCRIPTIONS if d.key == "power")
    data = DummySingleData(data=250.0)
    access = DummyAccess()
    sensor = HabuSingleSensor(
        data,
        serial_number=TEST_SERIAL_NUMBER,
        sensor_type="power",
        access=access,
        description=desc,
    )
    assert sensor.native_value == "250.0"
    sensor_none_data = DummySingleData(data=None)
    sensor_none = HabuSingleSensor(
        sensor_none_data,
        serial_number=TEST_SERIAL_NUMBER,
        sensor_type="power",
        access=access,
        description=desc,
    )
    assert sensor_none.native_value == "0.0"
    assert sensor.unique_id == f"power_sensor_{TEST_SERIAL_NUMBER}"


@pytest.mark.asyncio
async def test_setup_sensors_success(
    monkeypatch: pytest.MonkeyPatch,
    stub_async_create_task,
    hass_with_runtime: HomeAssistant,
    entry,
    runtime,
) -> None:
    """Test successful setup of sensors with runtime data."""

    await asyncio.sleep(0)

    added = []

    def add_entities(entities, update_before_add=False):
        added.extend(entities)
        assert update_before_add

    await setup_sensors(
        hass_with_runtime,
        TEST_SERIAL_NUMBER,
        add_entities,
        entry,
    )
    assert len(added) == 8

    expected_subscriptions = [
        f"/greencell/evse/{TEST_SERIAL_NUMBER}/current",
        f"/greencell/evse/{TEST_SERIAL_NUMBER}/voltage",
        f"/greencell/evse/{TEST_SERIAL_NUMBER}/power",
        f"/greencell/evse/{TEST_SERIAL_NUMBER}/status",
        f"/greencell/evse/{TEST_SERIAL_NUMBER}/device_state",
    ]

    assert len(hass_with_runtime.subscriptions) == len(expected_subscriptions)
    for topic in expected_subscriptions:
        assert topic in hass_with_runtime.subscriptions


@pytest.mark.asyncio
async def test_parse_voltage_success(
    monkeypatch: pytest.MonkeyPatch,
    stub_async_create_task,
    hass_with_runtime: HomeAssistant,
    entry,
    runtime,
) -> None:
    """Test successful parsing of voltage data and sensor setup."""

    await asyncio.sleep(0)

    added = []

    def add_entities(entities, update_before_add=False):
        added.extend(entities)
        assert update_before_add

    await setup_sensors(
        hass_with_runtime,
        TEST_SERIAL_NUMBER,
        add_entities,
        entry,
    )
    assert len(added) == 8

    voltage_callback = hass_with_runtime.subscriptions[
        f"/greencell/evse/{TEST_SERIAL_NUMBER}/voltage"
    ]

    def fake_voltage_parse_3phase(payload, obj):
        obj._values = {"l1": 230.0, "l2": 229.7, "l3": 232.5}

    monkeypatch.setattr(
        MqttParser, "parse_3phase_msg", staticmethod(fake_voltage_parse_3phase)
    )

    msg = SimpleNamespace(payload=b"dummy")
    voltage_callback(msg)

    for entity in added:
        if isinstance(entity, SensorEntity) and entity.unique_id.startswith("voltage_"):
            assert entity.native_value is not None
            expected_current = (
                "230.00"
                if entity.unique_id.startswith("voltage_l1")
                else "229.70"
                if entity.unique_id.startswith("voltage_l2")
                else "232.50"
                if entity.unique_id.startswith("voltage_l3")
                else None
            )

            assert entity.native_value == expected_current


@pytest.mark.asyncio
async def test_parse_current_msg(
    monkeypatch: pytest.MonkeyPatch,
    stub_async_create_task,
    hass_with_runtime: HomeAssistant,
    entry,
    runtime,
) -> None:
    """Test successful parsing of current data and sensor setup."""

    await asyncio.sleep(0)

    added = []

    def add_entities(entities, update_before_add=False):
        added.extend(entities)
        assert update_before_add

    await setup_sensors(
        hass_with_runtime,
        TEST_SERIAL_NUMBER,
        add_entities,
        entry,
    )
    assert len(added) == 8

    current_callback = hass_with_runtime.subscriptions[
        f"/greencell/evse/{TEST_SERIAL_NUMBER}/current"
    ]

    def fake_current_parse_3phase(payload, obj):
        obj._values = {"l1": 4000, "l2": 5000, "l3": 6000}

    monkeypatch.setattr(
        MqttParser, "parse_3phase_msg", staticmethod(fake_current_parse_3phase)
    )

    msg = SimpleNamespace(payload=b"dummy")
    current_callback(msg)

    for entity in added:
        if isinstance(entity, SensorEntity) and entity.unique_id.startswith("current_"):
            assert entity.native_value is not None
            expected_current = (
                "4.000"
                if entity.unique_id.startswith("current_l1")
                else "5.000"
                if entity.unique_id.startswith("current_l2")
                else "6.000"
                if entity.unique_id.startswith("current_l3")
                else None
            )

            assert entity.native_value == expected_current


@pytest.mark.asyncio
async def test_parse_power_success(
    monkeypatch: pytest.MonkeyPatch,
    stub_async_create_task,
    hass_with_runtime: HomeAssistant,
    entry,
    runtime,
) -> None:
    """Test successful parsing of voltage data and sensor setup."""

    await asyncio.sleep(0)

    added = []

    def add_entities(entities, update_before_add=False):
        added.extend(entities)
        assert update_before_add

    await setup_sensors(
        hass_with_runtime,
        TEST_SERIAL_NUMBER,
        add_entities,
        entry,
    )
    assert len(added) == 8

    power_callback = hass_with_runtime.subscriptions[
        f"/greencell/evse/{TEST_SERIAL_NUMBER}/power"
    ]

    def fake_power_parse_single(payload, key, obj):
        obj._value = 1500.5

    monkeypatch.setattr(
        MqttParser, "parse_single_phase_msg", staticmethod(fake_power_parse_single)
    )

    msg = SimpleNamespace(payload=b"dummy")
    power_callback(msg)

    # Verify that the sensor values were updated
    for entity in added:
        if isinstance(entity, SensorEntity) and entity.unique_id.startswith("power_"):
            assert entity.native_value is not None
            expected_power = "1500.5"
            assert entity.native_value == expected_power


@pytest.mark.asyncio
async def test_parse_state_success(
    monkeypatch: pytest.MonkeyPatch,
    stub_async_create_task,
    hass_with_runtime: HomeAssistant,
    entry,
    runtime,
) -> None:
    """Test successful parsing of state data and sensor setup."""

    await asyncio.sleep(0)

    added = []

    def add_entities(entities, update_before_add=False):
        added.extend(entities)
        assert update_before_add

    await setup_sensors(
        hass_with_runtime,
        TEST_SERIAL_NUMBER,
        add_entities,
        entry,
    )

    assert len(added) == 8

    state_callback = hass_with_runtime.subscriptions[
        f"/greencell/evse/{TEST_SERIAL_NUMBER}/status"
    ]

    def fake_state_parse_single(payload, key, obj):
        obj._value = "CHARGING"

    monkeypatch.setattr(
        MqttParser, "parse_single_phase_msg", staticmethod(fake_state_parse_single)
    )

    msg = SimpleNamespace(payload=b"dummy")
    state_callback(msg)

    for entity in added:
        if isinstance(entity, SensorEntity) and entity.unique_id.startswith("status_"):
            assert entity.native_value is not None
            expected_state = "CHARGING"
            assert entity.native_value == expected_state


@pytest.mark.asyncio
async def test_async_setup_platform_no_serial(
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant
) -> None:
    """Test async_setup_platform with no serial number in entry."""

    config = {}
    called = False

    async def fake_add(entities):
        nonlocal called
        called = True

    await async_setup_platform(hass, config, fake_add, discovery_info=None)
    assert not called


@pytest.mark.asyncio
async def test_async_setup_entry_no_serial(
    monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant
) -> None:
    """Test async_setup_entry with no serial number in entry data."""

    entry_missing = SimpleNamespace(entry_id="e2", data={})
    called = False

    async def fake_add(entities):
        nonlocal called
        called = True

    await async_setup_entry(hass, entry_missing, fake_add, discovery_info=None)
    assert not called
