"""Test offline conversion and interrupted registry ownership transfers."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import MappingProxyType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_test_home_assistant,
    mock_storage,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant import config_entries
from homeassistant.components.gree.const import CONF_IDENTIFIER, DOMAIN
from homeassistant.components.gree.discovery import device_info_to_data
from homeassistant.components.gree.migration import (
    _MIGRATION_LOCK,
    _child_entry_id,
    async_get_legacy_identifiers,
    async_migrate_legacy_entry,
    async_reconcile_migrated_entry,
)
from homeassistant.components.gree.switch import GREE_SWITCHES
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_INTEGRATION_DISCOVERY,
    SOURCE_USER,
    ConfigEntry,
    ConfigEntryDisabler,
    ConfigEntryState,
    ConfigSubentry,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    category_registry as cr,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    issue_registry as ir,
    label_registry as lr,
)
from homeassistant.helpers.json import json_bytes
from homeassistant.setup import async_setup_component
from homeassistant.util.json import json_loads

from .common import build_device_info_mock, build_device_mock

pytestmark = pytest.mark.usefixtures("device_registry", "entity_registry")

_SOURCE = "_migration_source_entry_id"
_IDENTIFIERS = ("AA:BB:CC:00:00:01", "AA-BB-CC-00-00-02", "AABB.CC00.0003")
_CANONICAL = ("aabbcc000001", "aabbcc000002", "aabbcc000003")


@pytest.fixture(autouse=True)
async def setup_component(hass: HomeAssistant, discovery: MagicMock) -> None:
    """Initialize the component before helper tests can add migration children."""
    discovery.mock_devices = []
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()


def _legacy(
    hass: HomeAssistant, *, disabled_by: ConfigEntryDisabler | None = None
) -> MockConfigEntry:
    """Create an unloaded shared entry with user preferences."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        unique_id="gree",
        source=SOURCE_USER,
        title="My original Gree entry",
        data={},
        options={"retained": "option"},
        pref_disable_new_entities=True,
        pref_disable_polling=True,
        disabled_by=disabled_by,
    )
    entry.add_to_hass(hass)
    return entry


def _records(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entry: ConfigEntry,
    identifier: str,
) -> tuple[dr.DeviceEntry, list[er.RegistryEntry]]:
    """Create the durable identities and customizations of an offline unit."""
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, identifier)},
        connections={(dr.CONNECTION_NETWORK_MAC, identifier)},
        name=f"Unit {identifier}",
        model="Legacy model",
        sw_version="V1.7",
    )
    device = device_registry.async_update_device(
        device.id,
        name_by_user=f"Custom {identifier}",
        disabled_by=dr.DeviceEntryDisabler.USER,
        labels={"device-label"},
        area_id="device-area",
    )
    assert device is not None
    entities = [
        entity_registry.async_get_or_create(
            "climate", DOMAIN, identifier, config_entry=entry, device_id=device.id
        ),
        *(
            entity_registry.async_get_or_create(
                "switch",
                DOMAIN,
                f"{identifier}_{description.key}",
                config_entry=entry,
                device_id=device.id,
            )
            for description in GREE_SWITCHES
        ),
    ]
    entities = [
        entity_registry.async_update_entity(
            entity.entity_id,
            name=f"Custom {entity.entity_id}",
            area_id="entity-area",
            icon="mdi:air-conditioner",
            disabled_by=er.RegistryEntryDisabler.USER,
            hidden_by=er.RegistryEntryHider.USER,
            labels={"entity-label"},
        )
        for entity in entities
    ]
    entities[0] = entity_registry.async_update_entity_options(
        entities[0].entity_id, "sensor", {"precision": 2}
    )
    return device, entities


def _child(
    hass: HomeAssistant, source: ConfigEntry, identifier: str, raw_identifier: str
) -> MockConfigEntry:
    """Restore a child from an interrupted migration."""
    child = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        minor_version=1,
        unique_id=identifier,
        source=SOURCE_IMPORT,
        title="Already split",
        data={
            "host": None,
            "port": 7000,
            CONF_IDENTIFIER: raw_identifier,
            "name": None,
            "brand": None,
            "model": None,
            "version": None,
            "mid": None,
            _SOURCE: source.entry_id,
        },
    )
    child.add_to_hass(hass)
    return child


def _assert_records(
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device: dr.DeviceEntry,
    entities: list[er.RegistryEntry],
    owner: str,
) -> None:
    """Ownership is the only mutable record data in the conversion."""
    current_device = device_registry.async_get(device.id)
    assert current_device is not None
    assert current_device.config_entry_id == owner
    for field in (
        "id",
        "identifiers",
        "connections",
        "name",
        "name_by_user",
        "area_id",
        "labels",
        "disabled_by",
        "model",
        "sw_version",
    ):
        assert getattr(current_device, field) == getattr(device, field)
    for entity in entities:
        current = entity_registry.async_get(entity.entity_id)
        assert current is not None
        assert current.config_entry_id == owner
        for field in (
            "id",
            "entity_id",
            "unique_id",
            "device_id",
            "name",
            "icon",
            "area_id",
            "labels",
            "disabled_by",
            "hidden_by",
            "options",
        ):
            assert getattr(current, field) == getattr(entity, field)


async def test_split_offline_preserves_records(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device: MagicMock,
    discovery: MagicMock,
) -> None:
    """All records split offline; the representative keeps the original entry."""
    discovery.mock_devices = []
    source = _legacy(hass)
    records = [
        _records(device_registry, entity_registry, source, identifier)
        for identifier in reversed(_IDENTIFIERS)
    ]
    assert not await hass.config_entries.async_setup(source.entry_id)
    await hass.async_block_till_done()

    assert source.version == 2
    assert source.minor_version == 1
    assert source.unique_id == _CANONICAL[0]
    assert source.title == "My original Gree entry"
    assert source.source == SOURCE_USER
    assert source.options == {"retained": "option"}
    assert source.pref_disable_new_entities
    assert source.pref_disable_polling
    assert source.data == {
        "host": None,
        "port": 7000,
        CONF_IDENTIFIER: _IDENTIFIERS[0],
        "name": f"Unit {_IDENTIFIERS[0]}",
        "brand": None,
        "model": "Legacy model",
        "version": "V1.7",
        "mid": None,
    }
    for identifier, raw_identifier, (old_device, entities) in zip(
        reversed(_CANONICAL), reversed(_IDENTIFIERS), records, strict=True
    ):
        entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, identifier)
        assert entry is not None
        assert entry.data[CONF_IDENTIFIER] == raw_identifier
        assert entry.options == source.options
        assert entry.pref_disable_new_entities
        assert entry.pref_disable_polling
        _assert_records(
            device_registry, entity_registry, old_device, entities, entry.entry_id
        )
    children = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry is not source
    ]
    assert [entry.unique_id for entry in children] == list(_CANONICAL[1:])
    for child in children:
        assert child.data[_SOURCE] == source.entry_id
        assert child.title == f"Custom {child.data[CONF_IDENTIFIER]}"
        assert child.source == SOURCE_IMPORT
        assert child.state is ConfigEntryState.SETUP_RETRY
    device().bind.assert_not_awaited()


def _stored_state(hass: HomeAssistant) -> dict[str, Any]:
    """Serialize the three independently persisted stores through their real records."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    return json_loads(
        json_bytes(
            {
                config_entries.STORAGE_KEY: {
                    "version": config_entries.STORAGE_VERSION,
                    "minor_version": config_entries.STORAGE_VERSION_MINOR,
                    "data": {
                        "entries": [
                            entry.as_dict()
                            for entry in hass.config_entries.async_entries(DOMAIN)
                        ]
                    },
                },
                dr.STORAGE_KEY: {
                    "version": dr.STORAGE_VERSION_MAJOR,
                    "minor_version": dr.STORAGE_VERSION_MINOR,
                    "data": {
                        "devices": [
                            device.as_storage_fragment
                            for device in device_registry.devices
                        ],
                        "child_devices": [],
                        "deleted_devices": [],
                    },
                },
                er.STORAGE_KEY: {
                    "version": er.STORAGE_VERSION_MAJOR,
                    "minor_version": er.STORAGE_VERSION_MINOR,
                    "data": {
                        "entities": [
                            entity.as_storage_fragment
                            for entity in entity_registry.entities.values()
                        ],
                        "deleted_entities": [],
                        "settings": {"entity_id_parts": None},
                    },
                },
            }
        )
    )


def _assign_stored_owner(
    stored: dict[str, Any],
    source_id: str,
    owner_id: str,
    identifier: str,
    *,
    device: bool,
    entities: bool,
) -> None:
    """Replay independently persisted registry ownership changes."""
    device_rows = stored[dr.STORAGE_KEY]["data"]["devices"]
    device_row = next(
        row
        for row in device_rows
        if row["config_entry_id"] == source_id
        and [DOMAIN, identifier] in row["identifiers"]
    )
    if device:
        device_row["config_entry_id"] = owner_id
    if entities:
        for row in stored[er.STORAGE_KEY]["data"]["entities"]:
            if row["device_id"] == device_row["id"]:
                row["config_entry_id"] = owner_id


def _identity_snapshot(stored: dict[str, Any]) -> dict[str, Any]:
    """Project durable identity and customization with stable ownership labels."""
    entries = stored[config_entries.STORAGE_KEY]["data"]["entries"]
    devices = stored[dr.STORAGE_KEY]["data"]["devices"]
    entities = stored[er.STORAGE_KEY]["data"]["entities"]
    owners = {entry["entry_id"]: entry["unique_id"] for entry in entries}
    device_ids = {device["id"]: min(device["identifiers"])[1] for device in devices}
    entry_rows = []
    for entry in entries:
        data = entry["data"].copy()
        if _SOURCE in data:
            data[_SOURCE] = owners[data[_SOURCE]]
        entry_rows.append(
            {
                **{
                    key: entry[key]
                    for key in (
                        "unique_id",
                        "version",
                        "minor_version",
                        "title",
                        "source",
                        "options",
                        "pref_disable_new_entities",
                        "pref_disable_polling",
                        "disabled_by",
                    )
                },
                "data": data,
            }
        )
    return {
        "entries": sorted(entry_rows, key=lambda row: row["unique_id"]),
        "devices": sorted(
            [
                {
                    **{
                        key: device[key]
                        for key in (
                            "identifiers",
                            "connections",
                            "name",
                            "name_by_user",
                            "area_id",
                            "labels",
                            "disabled_by",
                            "model",
                            "sw_version",
                        )
                    },
                    "owner": owners[device["config_entry_id"]],
                }
                for device in devices
            ],
            key=lambda row: row["identifiers"],
        ),
        "entities": sorted(
            [
                {
                    **{
                        key: entity[key]
                        for key in (
                            "entity_id",
                            "unique_id",
                            "name",
                            "icon",
                            "area_id",
                            "labels",
                            "disabled_by",
                            "hidden_by",
                            "options",
                        )
                    },
                    "device": device_ids[entity["device_id"]],
                    "owner": owners[entity["config_entry_id"]],
                }
                for entity in entities
            ],
            key=lambda row: row["entity_id"],
        ),
    }


@asynccontextmanager
async def _restore(
    stored: dict[str, Any],
) -> AsyncGenerator[tuple[HomeAssistant, dr.DeviceRegistry, er.EntityRegistry]]:
    """Load serialized entries and registries into a fresh Home Assistant instance."""
    with mock_storage(stored):
        async with async_test_home_assistant(load_registries=False) as restored:
            try:
                await ar.async_load(restored)
                await cr.async_load(restored)
                await fr.async_load(restored)
                await lr.async_load(restored)
                await ir.async_load(restored)
                await restored.config_entries.async_initialize()
                dr.async_setup(restored)
                await dr.async_load(restored)
                await er.async_load(restored)
                yield restored, dr.async_get(restored), er.async_get(restored)
            finally:
                await restored.async_stop()


@pytest.mark.parametrize(
    ("registry_key", "records_key", "count"),
    [
        pytest.param(dr.STORAGE_KEY, "devices", 1, id="device-owned-by-child"),
        pytest.param(
            er.STORAGE_KEY,
            "entities",
            len(GREE_SWITCHES) + 1,
            id="entities-owned-by-child",
        ),
    ],
)
async def test_reconcile_both_partial_ownership_directions(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    registry_key: str,
    records_key: str,
    count: int,
) -> None:
    """Normal child setup repairs either independently persisted ownership direction."""
    source = _legacy(hass, disabled_by=ConfigEntryDisabler.USER)
    representative = _records(device_registry, entity_registry, source, _IDENTIFIERS[0])
    old_device, entities = _records(
        device_registry, entity_registry, source, _IDENTIFIERS[1]
    )
    child = _child(hass, source, _CANONICAL[1], _IDENTIFIERS[1])
    stored = _stored_state(hass)
    for row in stored[registry_key]["data"][records_key][-count:]:
        row["config_entry_id"] = child.entry_id
    assert _identity_snapshot(stored) == snapshot(name="interrupted")

    async with _restore(stored) as (restored, restored_devices, restored_entities):
        restored_child = restored.config_entries.async_get_known_entry(child.entry_id)
        restored_source = restored.config_entries.async_get_known_entry(source.entry_id)
        assert restored_child is not child
        assert restored_source is not source
        assert await async_setup_component(restored, DOMAIN, {})
        await restored.async_block_till_done()
        assert restored_child.state is ConfigEntryState.SETUP_RETRY
        _assert_records(
            restored_devices, restored_entities, old_device, entities, child.entry_id
        )
        async_reconcile_migrated_entry(restored, restored_child)
        await restored.config_entries.async_set_disabled_by(source.entry_id, None)
        await restored.async_block_till_done()
        assert restored_source.version == 2
        assert restored_source.unique_id == _CANONICAL[0]
        assert restored_source.entry_id == source.entry_id
        _assert_records(
            restored_devices, restored_entities, *representative, source.entry_id
        )
        _assert_records(
            restored_devices, restored_entities, old_device, entities, child.entry_id
        )
        assert len(restored.config_entries.async_entries(DOMAIN)) == 2
        assert _identity_snapshot(_stored_state(restored)) == snapshot(name="recovered")


@pytest.mark.parametrize("interrupt_after", [1, 2])
async def test_interrupted_add_and_between_groups(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    discovery: MagicMock,
    snapshot: SnapshotAssertion,
    interrupt_after: int,
) -> None:
    """A cancellation after adding any child leaves a safely resumable source."""
    discovery.mock_devices = []
    source = _legacy(hass)
    records = [
        _records(device_registry, entity_registry, source, identifier)
        for identifier in _IDENTIFIERS
    ]
    original_add = hass.config_entries.async_add
    added = 0

    async def interrupt(child: ConfigEntry) -> None:
        nonlocal added
        await original_add(child)
        added += 1
        if added == interrupt_after:
            raise asyncio.CancelledError

    with (
        patch.object(hass.config_entries, "async_add", side_effect=interrupt),
        pytest.raises(asyncio.CancelledError),
    ):
        await async_migrate_legacy_entry(hass, source)
    assert source.version == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == interrupt_after + 1
    await hass.async_block_till_done()
    for old_device, entities in records[1:]:
        owner = device_registry.async_get(old_device.id).config_entry_id
        _assert_records(device_registry, entity_registry, old_device, entities, owner)
    stored = _stored_state(hass)
    assert _identity_snapshot(stored) == snapshot(name="interrupted")
    async with _restore(stored) as (restored, restored_devices, restored_entities):
        assert await async_setup_component(restored, DOMAIN, {})
        await restored.async_block_till_done()
        restored_source = restored.config_entries.async_get_known_entry(source.entry_id)
        assert restored_source is not source
        assert restored_source.unique_id == _CANONICAL[0]
        assert restored_source.version == 2
        assert len(restored.config_entries.async_entries(DOMAIN)) == 3
        expected_entry_ids = [
            source.entry_id,
            *(
                _child_entry_id(source.entry_id, identifier)
                for identifier in _CANONICAL[1:]
            ),
        ]
        for identifier, (old_device, entities), expected_entry_id in zip(
            _CANONICAL, records, expected_entry_ids, strict=True
        ):
            entry = restored.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, identifier
            )
            assert entry is not None
            assert entry.entry_id == expected_entry_id
            _assert_records(
                restored_devices,
                restored_entities,
                old_device,
                entities,
                entry.entry_id,
            )
        assert _identity_snapshot(_stored_state(restored)) == snapshot(name="recovered")


@pytest.mark.parametrize(
    ("move_device", "move_entities"),
    [
        pytest.param(True, False, id="device-only-transfer"),
        pytest.param(False, True, id="entity-only-transfer"),
        pytest.param(True, True, id="both-transferred"),
    ],
)
async def test_recover_missing_child_entry_after_registry_save(
    hass: HomeAssistant,
    discovery: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    move_device: bool,
    move_entities: bool,
) -> None:
    """A source-only config store can recreate a child from proven registry owners."""
    source = _legacy(hass)
    representative = _records(device_registry, entity_registry, source, _IDENTIFIERS[0])
    missing_records = _records(
        device_registry, entity_registry, source, _IDENTIFIERS[1]
    )
    owner_id = _child_entry_id(source.entry_id, _CANONICAL[1])
    stored = _stored_state(hass)
    assert [
        row["entry_id"] for row in stored[config_entries.STORAGE_KEY]["data"]["entries"]
    ] == [source.entry_id]
    _assign_stored_owner(
        stored,
        source.entry_id,
        owner_id,
        _IDENTIFIERS[1],
        device=move_device,
        entities=move_entities,
    )
    discovery.mock_devices = []

    async with _restore(stored) as (restored, restored_devices, restored_entities):
        restored_source = restored.config_entries.async_get_known_entry(source.entry_id)
        assert await async_setup_component(restored, DOMAIN, {})
        await restored.async_block_till_done()

        child = restored.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, _CANONICAL[1]
        )
        assert child is not None
        assert child.entry_id == owner_id
        assert restored_source.version == 2
        _assert_records(
            restored_devices, restored_entities, *representative, source.entry_id
        )
        _assert_records(
            restored_devices, restored_entities, *missing_records, child.entry_id
        )

        dr.async_cleanup(restored, restored_devices, restored_entities)
        _assert_records(
            restored_devices, restored_entities, *missing_records, child.entry_id
        )


@pytest.mark.parametrize(
    ("identifiers", "connections"),
    [
        pytest.param({(DOMAIN, _IDENTIFIERS[1])}, set(), id="gree-identifier"),
        pytest.param(
            set(),
            {(dr.CONNECTION_NETWORK_MAC, _IDENTIFIERS[1])},
            id="mac-connection",
        ),
    ],
)
async def test_recover_device_only_orphan(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    discovery: MagicMock,
    entity_registry: er.EntityRegistry,
    identifiers: set[tuple[str, str]],
    connections: set[tuple[str, str]],
) -> None:
    """A device-only orphan is recovered from its original identity records."""
    source = _legacy(hass)
    representative = _records(device_registry, entity_registry, source, _IDENTIFIERS[0])
    missing_device = device_registry.async_get_or_create(
        config_entry_id=source.entry_id,
        identifiers=identifiers,
        connections=connections,
    )
    owner_id = _child_entry_id(source.entry_id, _CANONICAL[1])
    stored = _stored_state(hass)
    next(
        row
        for row in stored[dr.STORAGE_KEY]["data"]["devices"]
        if row["id"] == missing_device.id
    )["config_entry_id"] = owner_id
    discovery.mock_devices = []

    async with _restore(stored) as (restored, restored_devices, restored_entities):
        assert await async_setup_component(restored, DOMAIN, {})
        await restored.async_block_till_done()
        child = restored.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, _CANONICAL[1]
        )
        assert child is not None
        assert child.entry_id == owner_id
        _assert_records(
            restored_devices, restored_entities, *representative, source.entry_id
        )
        _assert_records(
            restored_devices, restored_entities, missing_device, [], child.entry_id
        )

        dr.async_cleanup(restored, restored_devices, restored_entities)
        _assert_records(
            restored_devices, restored_entities, missing_device, [], child.entry_id
        )


async def test_recover_entity_only_orphan(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    discovery: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """An entity-only orphan is recovered from its Gree unique ID."""
    source = _legacy(hass)
    _records(device_registry, entity_registry, source, _IDENTIFIERS[0])
    missing_entity = entity_registry.async_get_or_create(
        "climate", DOMAIN, _IDENTIFIERS[1], config_entry=source
    )
    owner_id = _child_entry_id(source.entry_id, _CANONICAL[1])
    stored = _stored_state(hass)
    entity_row = next(
        row
        for row in stored[er.STORAGE_KEY]["data"]["entities"]
        if row["unique_id"] == _IDENTIFIERS[1]
    )
    entity_row["config_entry_id"] = owner_id
    discovery.mock_devices = []

    async with _restore(stored) as (restored, restored_devices, restored_entities):
        assert await async_setup_component(restored, DOMAIN, {})
        await restored.async_block_till_done()
        child = restored.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, _CANONICAL[1]
        )
        assert child is not None
        assert child.entry_id == owner_id
        restored_entity = restored_entities.async_get(missing_entity.entity_id)
        assert restored_entity is not None
        assert restored_entity.config_entry_id == child.entry_id
        assert restored_entity.unique_id == missing_entity.unique_id
        assert not dr.async_entries_for_config_entry(restored_devices, child.entry_id)


async def test_recover_multiple_missing_child_entries(
    hass: HomeAssistant,
    discovery: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """One startup recreates every child whose config write was interrupted."""
    source = _legacy(hass)
    records = [
        _records(device_registry, entity_registry, source, identifier)
        for identifier in _IDENTIFIERS
    ]
    stored = _stored_state(hass)
    assert [
        row["entry_id"] for row in stored[config_entries.STORAGE_KEY]["data"]["entries"]
    ] == [source.entry_id]
    for identifier, raw_identifier in zip(
        _CANONICAL[1:], _IDENTIFIERS[1:], strict=True
    ):
        _assign_stored_owner(
            stored,
            source.entry_id,
            _child_entry_id(source.entry_id, identifier),
            raw_identifier,
            device=True,
            entities=True,
        )
    discovery.mock_devices = []

    async with _restore(stored) as (restored, restored_devices, restored_entities):
        restored_source = restored.config_entries.async_get_known_entry(source.entry_id)
        assert await async_setup_component(restored, DOMAIN, {})
        await restored.async_block_till_done()

        assert restored_source.version == 2
        assert len(restored.config_entries.async_entries(DOMAIN)) == 3
        expected_entry_ids = [
            source.entry_id,
            *(
                _child_entry_id(source.entry_id, identifier)
                for identifier in _CANONICAL[1:]
            ),
        ]
        for identifier, (old_device, entities), expected_entry_id in zip(
            _CANONICAL, records, expected_entry_ids, strict=True
        ):
            entry = restored.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, identifier
            )
            assert entry is not None
            assert entry.entry_id == expected_entry_id
            _assert_records(
                restored_devices,
                restored_entities,
                old_device,
                entities,
                entry.entry_id,
            )


@pytest.mark.parametrize(
    "owner_id",
    [
        pytest.param("unrelated-orphan", id="unrelated"),
        pytest.param(
            _child_entry_id("another-source", _CANONICAL[1]), id="other-source"
        ),
    ],
)
async def test_do_not_adopt_unrelated_or_other_source_orphans(
    hass: HomeAssistant,
    discovery: MagicMock,
    owner_id: str,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Only this source's deterministic owner ID authorizes orphan recovery."""
    source = _legacy(hass)
    _records(device_registry, entity_registry, source, _IDENTIFIERS[0])
    missing_records = _records(
        device_registry, entity_registry, source, _IDENTIFIERS[1]
    )
    stored = _stored_state(hass)
    _assign_stored_owner(
        stored,
        source.entry_id,
        owner_id,
        _IDENTIFIERS[1],
        device=True,
        entities=True,
    )
    discovery.mock_devices = []

    async with _restore(stored) as (restored, restored_devices, restored_entities):
        restored_source = restored.config_entries.async_get_known_entry(source.entry_id)
        assert await async_setup_component(restored, DOMAIN, {})
        await restored.async_block_till_done()

        assert restored_source.version == 2
        assert (
            restored.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, _CANONICAL[1]
            )
            is None
        )
        device = restored_devices.async_get(missing_records[0].id)
        assert device is not None
        assert device.config_entry_id == owner_id
        assert all(
            entity.config_entry_id == owner_id
            for entity in er.async_entries_for_device(
                restored_entities, device.id, include_disabled_entities=True
            )
        )


async def test_invalid_unrelated_orphan_does_not_block_migration(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Malformed orphan identities and foreign helpers cannot enroll devices."""
    source = _legacy(hass)
    representative = _records(device_registry, entity_registry, source, _IDENTIFIERS[0])
    orphan = device_registry.async_get_or_create(
        config_entry_id=source.entry_id, identifiers={(DOMAIN, "")}
    )
    unsupported = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "unsupported", config_entry=source, device_id=orphan.id
    )
    helper = entity_registry.async_get_or_create(
        "sensor", "template", "helper", device_id=orphan.id
    )
    stored = _stored_state(hass)
    _assign_stored_owner(
        stored,
        source.entry_id,
        "unrelated-orphan",
        "",
        device=True,
        entities=True,
    )
    next(
        row
        for row in stored[er.STORAGE_KEY]["data"]["entities"]
        if row["entity_id"] == helper.entity_id
    )["config_entry_id"] = None

    async with _restore(stored) as (restored, restored_devices, restored_entities):
        assert await async_setup_component(restored, DOMAIN, {})
        await restored.async_block_till_done()
        restored_source = restored.config_entries.async_get_known_entry(source.entry_id)
        assert restored_source.version == 2
        assert restored.config_entries.async_entries(DOMAIN) == [restored_source]
        _assert_records(
            restored_devices, restored_entities, *representative, source.entry_id
        )
        _assert_records(
            restored_devices,
            restored_entities,
            orphan,
            [unsupported],
            "unrelated-orphan",
        )
        assert restored_entities.async_get(helper.entity_id).device_id == orphan.id


async def test_orphan_identity_conflict_fails_without_mutations(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A deterministic owner cannot transfer a device for a different identity."""
    source = _legacy(hass)
    for identifier in _IDENTIFIERS:
        _records(device_registry, entity_registry, source, identifier)
    stored = _stored_state(hass)
    owner_id = _child_entry_id(source.entry_id, _CANONICAL[1])
    _assign_stored_owner(
        stored,
        source.entry_id,
        owner_id,
        _IDENTIFIERS[1],
        device=False,
        entities=True,
    )
    _assign_stored_owner(
        stored,
        source.entry_id,
        owner_id,
        _IDENTIFIERS[2],
        device=True,
        entities=False,
    )

    async with _restore(stored) as (restored, restored_devices, restored_entities):
        restored_source = restored.config_entries.async_get_known_entry(source.entry_id)
        await _assert_rejected(
            restored,
            restored_devices,
            restored_entities,
            restored_source,
            match="Gree destination owns another device",
        )


async def test_disabled_source_waiting_for_migration_lock_is_unchanged(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A source disabled during its lock wait cannot transfer registry rows."""
    source = _legacy(hass)
    records = [
        _records(device_registry, entity_registry, source, identifier)
        for identifier in _IDENTIFIERS[:2]
    ]
    lock = hass.data.setdefault(_MIGRATION_LOCK, asyncio.Lock())
    await lock.acquire()
    migration = asyncio.create_task(async_migrate_legacy_entry(hass, source))
    await asyncio.sleep(0)
    try:
        await hass.config_entries.async_set_disabled_by(
            source.entry_id, ConfigEntryDisabler.USER
        )
    finally:
        lock.release()
    await migration
    await hass.async_block_till_done()

    assert source.version == 1
    assert source.disabled_by is ConfigEntryDisabler.USER
    assert hass.config_entries.async_entries(DOMAIN) == [source]
    for old_device, entities in records:
        _assert_records(
            device_registry, entity_registry, old_device, entities, source.entry_id
        )


async def test_add_reconciles_before_setup_or_await(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    discovery: MagicMock,
) -> None:
    """Registry transfer precedes the child's first network/setup suspension."""
    discovery.mock_devices = []
    source = _legacy(hass)
    _records(device_registry, entity_registry, source, _IDENTIFIERS[0])
    old_device, entities = _records(
        device_registry, entity_registry, source, _IDENTIFIERS[1]
    )

    def waiting_for_discovery(message: str) -> ConfigEntryNotReady:
        child = hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, _CANONICAL[1]
        )
        assert child is not None
        _assert_records(
            device_registry, entity_registry, old_device, entities, child.entry_id
        )
        return ConfigEntryNotReady(message)

    with patch(
        "homeassistant.components.gree.ConfigEntryNotReady",
        side_effect=waiting_for_discovery,
    ) as not_ready:
        assert not await hass.config_entries.async_setup(source.entry_id)
        assert not_ready.call_count == 2
        await hass.async_block_till_done()
        child = hass.config_entries.async_entry_for_domain_unique_id(
            DOMAIN, _CANONICAL[1]
        )
        assert child is not None
        _assert_records(
            device_registry, entity_registry, old_device, entities, child.entry_id
        )
    assert source.version == 2


@pytest.mark.parametrize(
    ("domain", "suffix"), [("climate", ""), ("switch", "_Health mode")]
)
async def test_entity_only_source(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    domain: str,
    suffix: str,
) -> None:
    """No physical-device row or address is needed to preserve an entity."""
    source = _legacy(hass)
    entity = entity_registry.async_get_or_create(
        domain,
        DOMAIN,
        f"{_IDENTIFIERS[0]}{suffix}",
        config_entry=source,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await async_migrate_legacy_entry(hass, source)
    assert source.version == 2
    assert source.unique_id == _CANONICAL[0]
    assert source.data[CONF_IDENTIFIER] == _IDENTIFIERS[0]
    assert source.data["host"] is None
    assert entity_registry.async_get(entity.entity_id) == entity


async def test_empty_source_is_retained(hass: HomeAssistant) -> None:
    """An empty legacy entry remains available as a discovery anchor."""
    source = _legacy(hass)
    await async_migrate_legacy_entry(hass, source)
    await hass.async_block_till_done()
    assert source.version == 1
    assert hass.config_entries.async_get_entry(source.entry_id) is source


async def test_empty_legacy_anchor_survives_restart_and_offers_returning_device(
    hass: HomeAssistant,
    device: MagicMock,
    discovery: MagicMock,
) -> None:
    """A retained v1 source starts without devices and still offers discovery."""
    source = _legacy(hass)
    stored = _stored_state(hass)
    discovery.mock_devices = [device()]

    async with _restore(stored) as (restored, restored_devices, restored_entities):
        restored_source = restored.config_entries.async_get_known_entry(source.entry_id)
        assert await async_setup_component(restored, DOMAIN, {})
        await restored.async_block_till_done(wait_background_tasks=True)

        assert restored_source.version == 1
        assert restored_source.state is ConfigEntryState.LOADED
        assert restored.config_entries.async_entries(DOMAIN) == [restored_source]
        flows = restored.config_entries.flow.async_progress()
        assert len(flows) == 1
        assert flows[0]["step_id"] == "discovery_confirm"
        assert flows[0]["context"]["unique_id"] == device().device_info.mac
        assert not restored_devices.devices
        assert not restored_entities.entities
        assert not restored.states.async_all("climate")
        device().bind.assert_not_awaited()
        device().update_state.assert_not_awaited()


async def _assert_rejected(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    source: ConfigEntry,
    *,
    match: str | None = None,
) -> None:
    """Assert preflight failures do not partially migrate any earlier group."""
    before_entries = hass.config_entries.async_entries(DOMAIN)
    before_devices = {device.id: device for device in device_registry.devices}
    before_entities = dict(entity_registry.entities)
    with pytest.raises(HomeAssistantError, match=match):
        await async_migrate_legacy_entry(hass, source)
    assert source.version == 1
    assert source.data == {}
    assert hass.config_entries.async_entries(DOMAIN) == before_entries
    assert {device.id: device for device in device_registry.devices} == before_devices
    assert dict(entity_registry.entities) == before_entities


@pytest.mark.parametrize(
    ("domain", "platform", "unique_id"),
    [
        pytest.param("sensor", DOMAIN, _IDENTIFIERS[-1], id="unsupported-domain"),
        pytest.param("climate", "other", _IDENTIFIERS[-1], id="foreign-platform"),
        pytest.param(
            "switch", DOMAIN, f"{_IDENTIFIERS[-1]}_Unknown", id="unknown-switch-suffix"
        ),
        pytest.param(
            "switch", DOMAIN, f"{_CANONICAL[-1]}_Quiet", id="ambiguous-raw-spelling"
        ),
        pytest.param("climate", DOMAIN, "", id="empty-identifier"),
    ],
)
async def test_invalid_entity_preflight(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    domain: str,
    platform: str,
    unique_id: str,
) -> None:
    """Invalid entity records prevent all transfers."""
    source = _legacy(hass)
    for identifier in _IDENTIFIERS:
        _records(device_registry, entity_registry, source, identifier)
    entity_registry.async_get_or_create(
        domain, platform, unique_id, config_entry=source
    )
    await _assert_rejected(hass, device_registry, entity_registry, source)


async def test_conflicting_entity_device_preflight(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A row linked to another identifier's physical device is not guessed or moved."""
    source = _legacy(hass)
    records = [
        _records(device_registry, entity_registry, source, identifier)
        for identifier in _IDENTIFIERS
    ]
    entity_registry.async_update_entity(
        records[-1][1][0].entity_id, device_id=records[0][0].id
    )
    await _assert_rejected(hass, device_registry, entity_registry, source)


async def test_foreign_device_ownership_preflight(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A legacy entity cannot transfer a device owned by an unrelated entry."""
    source = _legacy(hass)
    records = [
        _records(device_registry, entity_registry, source, identifier)
        for identifier in _IDENTIFIERS
    ]
    other = MockConfigEntry(domain="other")
    other.add_to_hass(hass)
    foreign_device = device_registry.async_get_or_create(
        config_entry_id=other.entry_id, identifiers={("other", "unit")}
    )
    entity_registry.async_update_entity(
        records[-1][1][0].entity_id, device_id=foreign_device.id
    )
    await _assert_rejected(
        hass,
        device_registry,
        entity_registry,
        source,
        match="Unexpected Gree device ownership",
    )


async def test_foreign_entity_ownership_preflight(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A device shared with an unrelated entry cannot be transferred."""
    source = _legacy(hass)
    records = [
        _records(device_registry, entity_registry, source, identifier)
        for identifier in _IDENTIFIERS
    ]
    other = MockConfigEntry(domain="other")
    other.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "sensor", "other", "unit", config_entry=other, device_id=records[-1][0].id
    )
    await _assert_rejected(
        hass,
        device_registry,
        entity_registry,
        source,
        match="Conflicting Gree device identity",
    )


async def test_destination_collision_preflight(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A same-identifier entry without source provenance is never replaced."""
    source = _legacy(hass)
    for identifier in _IDENTIFIERS:
        _records(device_registry, entity_registry, source, identifier)
    MockConfigEntry(domain=DOMAIN, version=2, unique_id=_CANONICAL[-1]).add_to_hass(
        hass
    )
    await _assert_rejected(hass, device_registry, entity_registry, source)


async def test_deterministic_child_entry_id_collision_preflight(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """A foreign entry occupying a recovery ID blocks all registry changes."""
    source = _legacy(hass)
    for identifier in _IDENTIFIERS:
        _records(device_registry, entity_registry, source, identifier)
    collision = MockConfigEntry(
        domain="other",
        entry_id=_child_entry_id(source.entry_id, _CANONICAL[1]),
    )
    collision.add_to_hass(hass)
    await _assert_rejected(
        hass,
        device_registry,
        entity_registry,
        source,
        match="entry ID is already in use",
    )


@pytest.mark.parametrize(
    ("version", "unique_id", "identifier", "error"),
    [
        pytest.param(
            1,
            _CANONICAL[-1],
            _IDENTIFIERS[-1],
            "Invalid Gree migration destination",
            id="legacy-version",
        ),
        pytest.param(
            2,
            None,
            _IDENTIFIERS[-1],
            "Invalid Gree migration destination",
            id="missing-unique-id",
        ),
        pytest.param(
            2,
            _CANONICAL[-1],
            None,
            "Invalid legacy Gree identifier",
            id="missing-identifier",
        ),
    ],
)
async def test_invalid_destination_preflight(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    version: int,
    unique_id: str | None,
    identifier: str | None,
    error: str,
) -> None:
    """An invalid interrupted destination blocks every ownership change."""
    source = _legacy(hass)
    for raw_identifier in _IDENTIFIERS:
        _records(device_registry, entity_registry, source, raw_identifier)
    child = _child(hass, source, _CANONICAL[-1], _IDENTIFIERS[-1])
    hass.config_entries.async_update_entry(
        child,
        version=version,
        unique_id=unique_id,
        data={**child.data, CONF_IDENTIFIER: identifier},
    )
    await _assert_rejected(hass, device_registry, entity_registry, source, match=error)


async def test_duplicate_destination_preflight(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Duplicate interrupted destinations cannot steal each other's records."""
    source = _legacy(hass)
    for identifier in _IDENTIFIERS:
        _records(device_registry, entity_registry, source, identifier)
    _child(hass, source, _CANONICAL[-1], _IDENTIFIERS[-1])
    _child(hass, source, _CANONICAL[-1], _IDENTIFIERS[-1])
    await _assert_rejected(
        hass,
        device_registry,
        entity_registry,
        source,
        match="Duplicate Gree migration destination",
    )


async def test_duplicate_physical_device_preflight(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Two physical rows for canonical-equivalent identifiers cannot be merged."""
    source = _legacy(hass)
    for identifier in _IDENTIFIERS:
        _records(device_registry, entity_registry, source, identifier)
    device_registry.async_get_or_create(
        config_entry_id=source.entry_id, identifiers={(DOMAIN, _CANONICAL[-1])}
    )
    await _assert_rejected(hass, device_registry, entity_registry, source)


async def test_child_device_preflight(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Unsupported child ownership cannot leave a partially migrated source."""
    source = _legacy(hass)
    records = [
        _records(device_registry, entity_registry, source, identifier)
        for identifier in _IDENTIFIERS
    ]
    device_registry.async_get_or_create_child(
        config_entry_id=source.entry_id,
        parent_device_id=records[-1][0].id,
        identifiers={(DOMAIN, "child")},
    )
    await _assert_rejected(hass, device_registry, entity_registry, source)


async def test_device_subentry_preflight(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Unexpected subentry ownership is not discarded during device migration."""
    source = _legacy(hass)
    for identifier in _IDENTIFIERS[:2]:
        _records(device_registry, entity_registry, source, identifier)
    subentry = ConfigSubentry(
        data=MappingProxyType({}),
        subentry_type="device",
        title="Legacy subentry",
        unique_id=None,
    )
    hass.config_entries.async_add_subentry(source, subentry)
    device_registry.async_get_or_create(
        config_entry_id=source.entry_id,
        config_subentry_id=subentry.subentry_id,
        identifiers={(DOMAIN, _IDENTIFIERS[-1])},
    )
    await _assert_rejected(
        hass,
        device_registry,
        entity_registry,
        source,
        match="Legacy Gree child-device ownership is unsupported",
    )


async def test_disabled_legacy_reserved_until_enabled(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    discovery: MagicMock,
) -> None:
    """Disabled entries reserve identifiers without enabling user-disabled rows."""
    discovery.mock_devices = []
    source = _legacy(hass, disabled_by=ConfigEntryDisabler.USER)
    records = [
        _records(device_registry, entity_registry, source, identifier)
        for identifier in _IDENTIFIERS[:2]
    ]
    assert async_get_legacy_identifiers(hass) == set(_CANONICAL[:2])
    assert source.version == 1
    assert source.disabled_by is ConfigEntryDisabler.USER
    await hass.config_entries.async_set_disabled_by(source.entry_id, None)
    await hass.async_block_till_done()
    assert source.version == 2
    assert async_get_legacy_identifiers(hass) == set()
    for identifier, (old_device, entities) in zip(_CANONICAL[:2], records, strict=True):
        entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, identifier)
        assert entry is not None
        _assert_records(
            device_registry, entity_registry, old_device, entities, entry.entry_id
        )


async def test_legacy_inventory_skips_invalid_records(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Malformed rows do not prevent discovery from reserving valid identities."""
    source = _legacy(hass)
    invalid_device = device_registry.async_get_or_create(
        config_entry_id=source.entry_id, identifiers={(DOMAIN, ":-.")}
    )
    invalid_entity = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "unsupported", config_entry=source
    )
    device, entities = _records(
        device_registry, entity_registry, source, _IDENTIFIERS[0]
    )
    entity = entity_registry.async_get_or_create(
        "climate", DOMAIN, _IDENTIFIERS[1], config_entry=source
    )

    assert async_get_legacy_identifiers(hass) == set(_CANONICAL[:2])
    await _assert_rejected(hass, device_registry, entity_registry, source)
    _assert_records(device_registry, entity_registry, device, entities, source.entry_id)
    assert entity_registry.async_get(entity.entity_id) == entity

    device_registry.async_remove_device(invalid_device.id)
    entity_registry.async_remove(invalid_entity.entity_id)
    assert async_get_legacy_identifiers(hass) == set(_CANONICAL[:2])
    assert source.version == 1


async def test_existing_child_with_no_legacy_rows_is_not_empty(
    hass: HomeAssistant,
) -> None:
    """Existing children still require a representative owned by the source."""
    source = _legacy(hass)
    _child(hass, source, _CANONICAL[1], _IDENTIFIERS[1])
    with pytest.raises(HomeAssistantError, match="representative"):
        await async_migrate_legacy_entry(hass, source)
    await hass.async_block_till_done()
    assert hass.config_entries.async_get_entry(source.entry_id) is source
    assert source.version == 1


async def test_cancel_after_insert_before_child_setup(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """An inserted destination with no transfers is reused on the next attempt."""
    source = _legacy(hass)
    _records(device_registry, entity_registry, source, _IDENTIFIERS[0])
    old_device, entities = _records(
        device_registry, entity_registry, source, _IDENTIFIERS[1]
    )
    with (
        patch.object(
            hass.config_entries, "async_setup", side_effect=asyncio.CancelledError
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await async_migrate_legacy_entry(hass, source)
    child = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, _CANONICAL[1])
    assert child is not None
    assert source.version == 1
    _assert_records(
        device_registry, entity_registry, old_device, entities, source.entry_id
    )
    await async_migrate_legacy_entry(hass, source)
    await hass.async_block_till_done()
    assert source.version == 2
    assert (
        hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, _CANONICAL[1])
        is child
    )
    _assert_records(
        device_registry, entity_registry, old_device, entities, child.entry_id
    )


async def test_concurrent_migration_serialized(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    discovery: MagicMock,
) -> None:
    """Concurrent attempts do not create competing destinations."""
    discovery.mock_devices = []
    source = _legacy(hass)
    records = [
        _records(device_registry, entity_registry, source, identifier)
        for identifier in _IDENTIFIERS
    ]
    await asyncio.gather(
        async_migrate_legacy_entry(hass, source),
        async_migrate_legacy_entry(hass, source),
    )
    await hass.async_block_till_done()
    assert source.version == 2
    assert len(hass.config_entries.async_entries(DOMAIN)) == 3
    for identifier, (old_device, entities) in zip(_CANONICAL, records, strict=True):
        entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, identifier)
        assert entry is not None
        _assert_records(
            device_registry, entity_registry, old_device, entities, entry.entry_id
        )


@pytest.mark.parametrize(
    "identifiers",
    [
        pytest.param({(DOMAIN, _IDENTIFIERS[0])}, id="gree-identifier"),
        pytest.param(set(), id="network-connection"),
    ],
)
async def test_device_only_source(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    identifiers: set[tuple[str, str]],
) -> None:
    """Device-only legacy records are enrolled even with no surviving entities."""
    source = _legacy(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=source.entry_id,
        identifiers=identifiers,
        connections={(dr.CONNECTION_NETWORK_MAC, _IDENTIFIERS[0])},
    )
    await async_migrate_legacy_entry(hass, source)
    assert source.version == 2
    assert source.unique_id == _CANONICAL[0]
    assert source.data["host"] is None
    assert source.data["port"] == 7000
    assert device_registry.async_get(device.id) == device
    assert not er.async_entries_for_config_entry(entity_registry, source.entry_id)


async def test_entity_identity_precedes_device_spelling(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Canonical-equivalent identifiers must not rewrite exact entity prefixes."""
    source = _legacy(hass)
    old_device, entities = _records(
        device_registry, entity_registry, source, _IDENTIFIERS[0]
    )
    device_registry.async_update_device(
        old_device.id, new_identifiers={(DOMAIN, _CANONICAL[0])}
    )
    await async_migrate_legacy_entry(hass, source)
    assert source.data[CONF_IDENTIFIER] == _IDENTIFIERS[0]
    for entity in entities:
        assert entity_registry.async_get(entity.entity_id) == entity


@pytest.mark.parametrize(
    "entity_count",
    [
        pytest.param(len(GREE_SWITCHES) + 1, id="device-with-entities"),
        pytest.param(0, id="device-only"),
    ],
)
async def test_child_cannot_own_another_identity(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    entity_count: int,
) -> None:
    """Matching provenance does not authorize merging a child's unrelated rows."""
    source = _legacy(hass)
    for identifier in _IDENTIFIERS[:2]:
        _records(device_registry, entity_registry, source, identifier)
    child = _child(hass, source, _CANONICAL[1], _IDENTIFIERS[1])
    _, entities = _records(device_registry, entity_registry, child, _IDENTIFIERS[2])
    for entity in entities[entity_count:]:
        entity_registry.async_remove(entity.entity_id)
    await _assert_rejected(hass, device_registry, entity_registry, source)


async def test_entity_identity_without_device_identifiers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """An exact entity identity remains authoritative when device metadata is absent."""
    source = _legacy(hass)
    old_device, entities = _records(
        device_registry, entity_registry, source, _IDENTIFIERS[0]
    )
    device_registry.async_update_device(
        old_device.id, new_identifiers={("other", "unit-1")}, new_connections=set()
    )
    await async_migrate_legacy_entry(hass, source)
    assert source.data[CONF_IDENTIFIER] == _IDENTIFIERS[0]
    assert source.unique_id == _CANONICAL[0]
    for entity in entities:
        assert entity_registry.async_get(entity.entity_id) == entity


@pytest.mark.parametrize(
    ("registry_key", "records_key", "count"),
    [
        pytest.param(dr.STORAGE_KEY, "devices", 1, id="device-still-owned-by-source"),
        pytest.param(
            er.STORAGE_KEY,
            "entities",
            len(GREE_SWITCHES) + 1,
            id="entities-still-owned-by-source",
        ),
    ],
)
async def test_restored_migrated_child_repairs_and_loads_after_discovery(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    device: MagicMock,
    registry_key: str,
    records_key: str,
    count: int,
) -> None:
    """A migrated child repairs ownership and loads without changing durable identity."""
    source = _legacy(hass)
    representative = _records(device_registry, entity_registry, source, _IDENTIFIERS[0])
    old_device, entities = _records(
        device_registry, entity_registry, source, _IDENTIFIERS[1]
    )
    enabled_device = device_registry.async_update_device(
        old_device.id, disabled_by=None
    )
    assert enabled_device is not None
    entities = [
        entity_registry.async_update_entity(entity.entity_id, disabled_by=None)
        for entity in entities[:-1]
    ] + entities[-1:]
    assert not await hass.config_entries.async_setup(source.entry_id)
    await hass.async_block_till_done()
    child = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, _CANONICAL[1])
    assert child is not None
    assert source.version == 2
    assert child.state is ConfigEntryState.SETUP_RETRY
    _assert_records(
        device_registry, entity_registry, enabled_device, entities, child.entry_id
    )
    stored = _stored_state(hass)
    for row in stored[registry_key]["data"][records_key][-count:]:
        row["config_entry_id"] = source.entry_id

    async with _restore(stored) as (restored, restored_devices, restored_entities):
        assert await async_setup_component(restored, DOMAIN, {})
        await restored.async_block_till_done()
        restored_child = restored.config_entries.async_get_known_entry(child.entry_id)
        restored_source = restored.config_entries.async_get_known_entry(source.entry_id)
        assert restored_child is not child
        assert restored_source is not source
        assert restored_child.state is ConfigEntryState.SETUP_RETRY
        assert restored_source.unique_id == _CANONICAL[0]
        _assert_records(
            restored_devices,
            restored_entities,
            *representative,
            source.entry_id,
        )
        _assert_records(
            restored_devices,
            restored_entities,
            enabled_device,
            entities,
            child.entry_id,
        )
        online_device = build_device_mock(
            name=f"Unit {_IDENTIFIERS[1]}",
            ipAddress="192.0.2.42",
            identifier=_IDENTIFIERS[1],
        )
        device.return_value = online_device
        observed = build_device_info_mock(
            name=f"Unit {_IDENTIFIERS[1]}",
            ipAddress="192.0.2.42",
            identifier=_CANONICAL[1],
            model="Legacy model",
            version="V1.7",
        )
        result = await restored.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_INTEGRATION_DISCOVERY},
            data=device_info_to_data(observed),
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"
        await restored.async_block_till_done()
        assert restored_child.state is ConfigEntryState.LOADED
        assert restored_child.data[CONF_IDENTIFIER] == _IDENTIFIERS[1]
        assert restored_child.data["host"] == "192.0.2.42"
        assert restored_child.title == child.title
        assert restored_child.data[_SOURCE] == source.entry_id
        assert len(restored.config_entries.async_entries(DOMAIN)) == 2
        _assert_records(
            restored_devices,
            restored_entities,
            enabled_device,
            entities,
            child.entry_id,
        )
        assert {
            entity.id
            for entity in er.async_entries_for_config_entry(
                restored_entities, child.entry_id
            )
        } == {entity.id for entity in entities}
        for entity in entities[:-1]:
            state = restored.states.get(entity.entity_id)
            assert state is not None
            assert state.state != "unavailable"
        assert restored.states.get(entities[-1].entity_id) is None
        disabled_entity = restored_entities.async_get(entities[-1].entity_id)
        assert disabled_entity is not None
        assert disabled_entity.disabled_by is er.RegistryEntryDisabler.USER
        online_device.bind.assert_awaited_once()
        online_device.update_state.assert_awaited_once()
