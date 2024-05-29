"""Tests for the DSMR integration."""

import datetime
from decimal import Decimal

from homeassistant.components.dsmr.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry


async def test_migrate_gas_to_mbus(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    dsmr_connection_fixture,
) -> None:
    """Test migration of unique_id."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    from dsmr_parser.obis_references import (
        BELGIUM_MBUS1_DEVICE_TYPE,
        BELGIUM_MBUS1_EQUIPMENT_IDENTIFIER,
        BELGIUM_MBUS1_METER_READING2,
    )
    from dsmr_parser.objects import CosemObject, MBusObject

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

    telegram = {
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
    }

    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

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


async def test_migrate_gas_to_mbus_exists(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    dsmr_connection_fixture,
) -> None:
    """Test migration of unique_id."""
    (connection_factory, transport, protocol) = dsmr_connection_fixture

    from dsmr_parser.obis_references import (
        BELGIUM_MBUS1_DEVICE_TYPE,
        BELGIUM_MBUS1_EQUIPMENT_IDENTIFIER,
        BELGIUM_MBUS1_METER_READING2,
    )
    from dsmr_parser.objects import CosemObject, MBusObject

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

    telegram = {
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
    }

    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    telegram_callback = connection_factory.call_args_list[0][0][2]

    # simulate a telegram pushed from the smartmeter and parsed by dsmr_parser
    telegram_callback(telegram)

    # after receiving telegram entities need to have the chance to be created
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, old_unique_id)
        == "sensor.gas_meter_reading"
    )
