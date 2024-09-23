"""Tests for ScreenLogic integration init."""

from dataclasses import dataclass
from unittest.mock import DEFAULT, patch

import pytest
from screenlogicpy import ScreenLogicGateway

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.number import DOMAIN as NUMBER_DOMAIN
from homeassistant.components.screenlogic import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import slugify

from . import (
    DATA_MIN_MIGRATION,
    DATA_MISSING_VALUES_CHEM_CHLOR,
    GATEWAY_DISCOVERY_IMPORT_PATH,
    MOCK_ADAPTER_MAC,
    MOCK_ADAPTER_NAME,
    stub_async_connect,
)

from tests.common import MockConfigEntry


@dataclass
class EntityMigrationData:
    """Class to organize minimum entity data."""

    old_name: str
    old_key: str
    new_name: str
    new_key: str
    domain: str


TEST_MIGRATING_ENTITIES = [
    EntityMigrationData(
        "Chemistry Alarm",
        "chem_alarm",
        "Active Alert",
        "active_alert",
        BINARY_SENSOR_DOMAIN,
    ),
    EntityMigrationData(
        "Pool Low Pump Current Watts",
        "currentWatts_0",
        "Pool Low Pump Watts Now",
        "pump_0_watts_now",
        SENSOR_DOMAIN,
    ),
    EntityMigrationData(
        "SCG Status",
        "scg_status",
        "Chlorinator",
        "scg_state",
        BINARY_SENSOR_DOMAIN,
    ),
    EntityMigrationData(
        "Non-Migrating Sensor",
        "nonmigrating",
        "Non-Migrating Sensor",
        "nonmigrating",
        SENSOR_DOMAIN,
    ),
    EntityMigrationData(
        "Cyanuric Acid",
        "chem_cya",
        "Cyanuric Acid",
        "chem_cya",
        SENSOR_DOMAIN,
    ),
    EntityMigrationData(
        "Old Sensor",
        "old_sensor",
        "Old Sensor",
        "old_sensor",
        SENSOR_DOMAIN,
    ),
    EntityMigrationData(
        "Pump Sensor Missing Index",
        "currentWatts",
        "Pump Sensor Missing Index",
        "currentWatts",
        SENSOR_DOMAIN,
    ),
]


def _migration_connect(*args, **kwargs):
    return stub_async_connect(DATA_MIN_MIGRATION, *args, **kwargs)


@pytest.mark.parametrize(
    ("entity_def", "ent_data"),
    [
        (
            {
                "domain": ent_data.domain,
                "platform": DOMAIN,
                "unique_id": f"{MOCK_ADAPTER_MAC}_{ent_data.old_key}",
                "suggested_object_id": f"{MOCK_ADAPTER_NAME} {ent_data.old_name}",
                "disabled_by": None,
                "has_entity_name": True,
                "original_name": ent_data.old_name,
            },
            ent_data,
        )
        for ent_data in TEST_MIGRATING_ENTITIES
    ],
    ids=[ent_data.old_name for ent_data in TEST_MIGRATING_ENTITIES],
)
async def test_async_migrate_entries(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    entity_def: dict,
    ent_data: EntityMigrationData,
) -> None:
    """Test migration to new entity names."""
    mock_config_entry.add_to_hass(hass)

    device: dr.DeviceEntry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MOCK_ADAPTER_MAC)},
    )

    TEST_EXISTING_ENTRY = {
        "domain": SENSOR_DOMAIN,
        "platform": DOMAIN,
        "unique_id": f"{MOCK_ADAPTER_MAC}_cya",
        "suggested_object_id": f"{MOCK_ADAPTER_NAME} CYA",
        "disabled_by": None,
        "has_entity_name": True,
        "original_name": "CYA",
    }

    entity_registry.async_get_or_create(
        **TEST_EXISTING_ENTRY, device_id=device.id, config_entry=mock_config_entry
    )

    entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **entity_def, device_id=device.id, config_entry=mock_config_entry
    )

    old_eid = f"{ent_data.domain}.{slugify(f'{MOCK_ADAPTER_NAME} {ent_data.old_name}')}"
    old_uid = f"{MOCK_ADAPTER_MAC}_{ent_data.old_key}"
    new_eid = f"{ent_data.domain}.{slugify(f'{MOCK_ADAPTER_NAME} {ent_data.new_name}')}"
    new_uid = f"{MOCK_ADAPTER_MAC}_{ent_data.new_key}"

    assert entity.unique_id == old_uid
    assert entity.entity_id == old_eid

    with (
        patch(
            GATEWAY_DISCOVERY_IMPORT_PATH,
            return_value={},
        ),
        patch.multiple(
            ScreenLogicGateway,
            async_connect=_migration_connect,
            is_connected=True,
            _async_connected_request=DEFAULT,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(new_eid)
    assert entity_migrated
    assert entity_migrated.entity_id == new_eid
    assert entity_migrated.unique_id == new_uid
    assert entity_migrated.original_name == ent_data.new_name


async def test_entity_migration_data(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test ENTITY_MIGRATION data guards."""
    mock_config_entry.add_to_hass(hass)

    device: dr.DeviceEntry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, MOCK_ADAPTER_MAC)},
    )

    TEST_EXISTING_ENTRY = {
        "domain": SENSOR_DOMAIN,
        "platform": DOMAIN,
        "unique_id": f"{MOCK_ADAPTER_MAC}_missing_device",
        "suggested_object_id": f"{MOCK_ADAPTER_NAME} Missing Migration Device",
        "disabled_by": None,
        "has_entity_name": True,
        "original_name": "EMissing Migration Device",
    }

    original_entity: er.RegistryEntry = entity_registry.async_get_or_create(
        **TEST_EXISTING_ENTRY, device_id=device.id, config_entry=mock_config_entry
    )

    old_eid = original_entity.entity_id
    old_uid = original_entity.unique_id

    assert old_uid == f"{MOCK_ADAPTER_MAC}_missing_device"
    assert (
        old_eid
        == f"{SENSOR_DOMAIN}.{slugify(f'{MOCK_ADAPTER_NAME} Missing Migration Device')}"
    )

    # This patch simulates bad data being added to ENTITY_MIGRATIONS
    with (
        patch.dict(
            "homeassistant.components.screenlogic.data.ENTITY_MIGRATIONS",
            {
                "missing_device": {
                    "new_key": "state",
                    "old_name": "Missing Migration Device",
                    "new_name": "Bad ENTITY_MIGRATIONS Entry",
                },
            },
        ),
        patch(
            GATEWAY_DISCOVERY_IMPORT_PATH,
            return_value={},
        ),
        patch.multiple(
            ScreenLogicGateway,
            async_connect=_migration_connect,
            is_connected=True,
            _async_connected_request=DEFAULT,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_migrated = entity_registry.async_get(
        slugify(f"{MOCK_ADAPTER_NAME} Bad ENTITY_MIGRATIONS Entry")
    )
    assert entity_migrated is None

    entity_not_migrated = entity_registry.async_get(old_eid)
    assert entity_not_migrated == original_entity


async def test_platform_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup for platforms that define expected data."""

    def stub_connect(*args, **kwargs):
        return stub_async_connect(DATA_MISSING_VALUES_CHEM_CHLOR, *args, **kwargs)

    device_prefix = slugify(MOCK_ADAPTER_NAME)

    tested_entity_ids = [
        f"{BINARY_SENSOR_DOMAIN}.{device_prefix}_active_alert",
        f"{SENSOR_DOMAIN}.{device_prefix}_air_temperature",
        f"{NUMBER_DOMAIN}.{device_prefix}_pool_chlorinator_setpoint",
    ]

    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            GATEWAY_DISCOVERY_IMPORT_PATH,
            return_value={},
        ),
        patch.multiple(
            ScreenLogicGateway,
            async_connect=stub_connect,
            is_connected=True,
            _async_connected_request=DEFAULT,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        for entity_id in tested_entity_ids:
            assert hass.states.get(entity_id) is not None
