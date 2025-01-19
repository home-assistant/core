"""Tests for the DSMR integration."""

import datetime
from decimal import Decimal
from unittest.mock import MagicMock

from dsmr_parser.obis_references import (
    MBUS_DEVICE_TYPE,
    MBUS_EQUIPMENT_IDENTIFIER,
    MBUS_METER_READING,
)
from dsmr_parser.objects import CosemObject, MBusObject, Telegram
import pytest

from homeassistant.components.dsmr.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_migrate_gas_to_mbus(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test migration of unique_id."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="/dev/ttyUSB0",
        data={
            "port": "/dev/ttyUSB0",
            "dsmr_version": "5B",
            "serial_id": "1234",
            "serial_id_gas": "37464C4F32313139303333373331",
        },
        options={
            "time_between_update": 0,
        },
    )

    mock_entry.add_to_hass(hass)

    old_unique_id = "37464C4F32313139303333373331_belgium_5min_gas_meter_reading"

    device = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={(DOMAIN, mock_entry.entry_id)},
        name="Gas Meter",
    )
    await hass.async_block_till_done()

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        suggested_object_id="gas_meter_reading",
        disabled_by=None,
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        device_id=device.id,
        unique_id=old_unique_id,
        config_entry=mock_entry,
    )
    assert entity.unique_id == old_unique_id
    await hass.async_block_till_done()

    telegram = Telegram()
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
                {"value": Decimal(745.695), "unit": "m3"},
            ],
        ),
        "MBUS_METER_READING",
    )

    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    # Check a new device is created and the old device has been removed
    assert len(device_registry.devices) == 1
    assert not device_registry.async_get(device.id)
    new_entity = entity_registry.async_get("sensor.gas_meter_reading")
    new_device = device_registry.async_get(new_entity.device_id)
    new_dev_entities = er.async_entries_for_device(
        entity_registry, new_device.id, include_disabled_entities=True
    )
    assert new_dev_entities == [new_entity]

    # Check no entities are connected to the old device
    dev_entities = er.async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    )
    assert not dev_entities

    assert (
        entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, old_unique_id)
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, "37464C4F32313139303333373331"
        )
        == "sensor.gas_meter_reading"
    )


async def test_migrate_hourly_gas_to_mbus(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test migration of unique_id."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="/dev/ttyUSB0",
        data={
            "port": "/dev/ttyUSB0",
            "dsmr_version": "5",
            "serial_id": "1234",
            "serial_id_gas": "4730303738353635363037343639323231",
        },
        options={
            "time_between_update": 0,
        },
    )

    mock_entry.add_to_hass(hass)

    old_unique_id = "4730303738353635363037343639323231_hourly_gas_meter_reading"

    device = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={(DOMAIN, mock_entry.entry_id)},
        name="Gas Meter",
    )
    await hass.async_block_till_done()

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        suggested_object_id="gas_meter_reading",
        disabled_by=None,
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        device_id=device.id,
        unique_id=old_unique_id,
        config_entry=mock_entry,
    )
    assert entity.unique_id == old_unique_id
    await hass.async_block_till_done()

    telegram = Telegram()
    telegram.add(
        MBUS_DEVICE_TYPE,
        CosemObject((0, 1), [{"value": "003", "unit": ""}]),
        "MBUS_DEVICE_TYPE",
    )
    telegram.add(
        MBUS_EQUIPMENT_IDENTIFIER,
        CosemObject(
            (0, 1),
            [{"value": "4730303738353635363037343639323231", "unit": ""}],
        ),
        "MBUS_EQUIPMENT_IDENTIFIER",
    )
    telegram.add(
        MBUS_METER_READING,
        MBusObject(
            (0, 1),
            [
                {"value": datetime.datetime.fromtimestamp(1722749707)},
                {"value": Decimal(778.963), "unit": "m3"},
            ],
        ),
        "MBUS_METER_READING",
    )

    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    # Check a new device is created and the old device has been removed
    assert len(device_registry.devices) == 1
    assert not device_registry.async_get(device.id)
    new_entity = entity_registry.async_get("sensor.gas_meter_reading")
    new_device = device_registry.async_get(new_entity.device_id)
    new_dev_entities = er.async_entries_for_device(
        entity_registry, new_device.id, include_disabled_entities=True
    )
    assert new_dev_entities == [new_entity]

    # Check no entities are connected to the old device
    dev_entities = er.async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    )
    assert not dev_entities

    assert (
        entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, old_unique_id)
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, "4730303738353635363037343639323231"
        )
        == "sensor.gas_meter_reading"
    )


async def test_migrate_gas_with_devid_to_mbus(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
) -> None:
    """Test migration of unique_id."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="/dev/ttyUSB0",
        data={
            "port": "/dev/ttyUSB0",
            "dsmr_version": "5B",
            "serial_id": "1234",
            "serial_id_gas": "37464C4F32313139303333373331",
        },
        options={
            "time_between_update": 0,
        },
    )

    mock_entry.add_to_hass(hass)

    old_unique_id = "37464C4F32313139303333373331_belgium_5min_gas_meter_reading"

    device = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={(DOMAIN, "37464C4F32313139303333373331")},
        name="Gas Meter",
    )
    await hass.async_block_till_done()

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        suggested_object_id="gas_meter_reading",
        disabled_by=None,
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        device_id=device.id,
        unique_id=old_unique_id,
        config_entry=mock_entry,
    )
    assert entity.unique_id == old_unique_id
    await hass.async_block_till_done()

    telegram = Telegram()
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
                {"value": Decimal(745.695), "unit": "m3"},
            ],
        ),
        "MBUS_METER_READING",
    )

    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    # Check a new device is not created and the old device has not been removed
    assert len(device_registry.devices) == 1
    assert device_registry.async_get(device.id)
    new_entity = entity_registry.async_get("sensor.gas_meter_reading")
    new_device = device_registry.async_get(new_entity.device_id)
    assert new_device.id == device.id
    # Check entities are still connected to the old device
    dev_entities = er.async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    )
    assert dev_entities == [new_entity]

    assert (
        entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, old_unique_id)
        is None
    )
    assert (
        entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, "37464C4F32313139303333373331"
        )
        == "sensor.gas_meter_reading"
    )


async def test_migrate_gas_to_mbus_exists(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    dsmr_connection_fixture: tuple[MagicMock, MagicMock, MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test migration of unique_id."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="/dev/ttyUSB0",
        data={
            "port": "/dev/ttyUSB0",
            "dsmr_version": "5B",
            "serial_id": "1234",
            "serial_id_gas": "37464C4F32313139303333373331",
        },
        options={
            "time_between_update": 0,
        },
    )

    mock_entry.add_to_hass(hass)

    old_unique_id = "37464C4F32313139303333373331_belgium_5min_gas_meter_reading"

    device = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={(DOMAIN, mock_entry.entry_id)},
        name="Gas Meter",
    )
    await hass.async_block_till_done()

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        suggested_object_id="gas_meter_reading",
        disabled_by=None,
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        device_id=device.id,
        unique_id=old_unique_id,
        config_entry=mock_entry,
    )
    assert entity.unique_id == old_unique_id

    device2 = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={(DOMAIN, "37464C4F32313139303333373331")},
        name="Gas Meter",
    )
    await hass.async_block_till_done()

    entity_registry.async_get_or_create(
        suggested_object_id="gas_meter_reading_alt",
        disabled_by=None,
        domain=SENSOR_DOMAIN,
        platform=DOMAIN,
        device_id=device2.id,
        unique_id="37464C4F32313139303333373331",
        config_entry=mock_entry,
    )
    await hass.async_block_till_done()

    telegram = Telegram()
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
                {"value": Decimal(745.695), "unit": "m3"},
            ],
        ),
        "MBUS_METER_READING",
    )

    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    # Check a new device is not created and the old device has not been removed
    assert len(device_registry.devices) == 2
    assert device_registry.async_get(device.id)
    assert device_registry.async_get(device2.id)
    entity = entity_registry.async_get("sensor.gas_meter_reading")
    dev_entities = er.async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    )
    assert dev_entities == [entity]
    entity2 = entity_registry.async_get("sensor.gas_meter_reading_alt")
    dev2_entities = er.async_entries_for_device(
        entity_registry, device2.id, include_disabled_entities=True
    )
    assert dev2_entities == [entity2]

    assert (
        entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, old_unique_id)
        == "sensor.gas_meter_reading"
    )
    assert (
        entity_registry.async_get_entity_id(
            SENSOR_DOMAIN, DOMAIN, "37464C4F32313139303333373331"
        )
        == "sensor.gas_meter_reading_alt"
    )
    assert (
        "Skip migration of sensor.gas_meter_reading because it already exists"
        in caplog.text
    )
