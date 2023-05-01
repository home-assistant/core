"""Tests for the collection helper."""
from __future__ import annotations

import logging

import pytest
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    collection,
    entity_component,
    entity_registry as er,
    storage,
)
from homeassistant.helpers.typing import ConfigType

from tests.common import flush_store
from tests.typing import WebSocketGenerator

_LOGGER = logging.getLogger(__name__)


def track_changes(coll: collection.ObservableCollection):
    """Create helper to track changes in a collection."""
    changes = []

    async def listener(*args):
        changes.append(args)

    coll.async_add_listener(listener)

    return changes


class MockEntity(collection.CollectionEntity):
    """Entity that is config based."""

    def __init__(self, config):
        """Initialize entity."""
        self._config = config

    @classmethod
    def from_storage(cls, config: ConfigType) -> MockEntity:
        """Create instance from storage."""
        return cls(config)

    @classmethod
    def from_yaml(cls, config: ConfigType) -> MockEntity:
        """Create instance from storage."""
        raise NotImplementedError

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._config["id"]

    @property
    def name(self):
        """Return name of entity."""
        return self._config["name"]

    @property
    def state(self):
        """Return state of entity."""
        return self._config["state"]

    async def async_update_config(self, config):
        """Update entity config."""
        self._config = config
        self.async_write_ha_state()


class MockObservableCollection(collection.ObservableCollection):
    """Mock observable collection which can create entities."""

    @staticmethod
    def create_entity(
        entity_class: type[collection.CollectionEntity], config: ConfigType
    ) -> collection.CollectionEntity:
        """Create a CollectionEntity instance."""
        return entity_class.from_storage(config)


class MockStorageCollection(collection.DictStorageCollection):
    """Mock storage collection."""

    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        if "name" not in data:
            raise ValueError("invalid")

        return data

    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return info["name"]

    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        return {**item, **update_data}


def test_id_manager() -> None:
    """Test the ID manager."""
    id_manager = collection.IDManager()
    assert not id_manager.has_id("some_id")
    data = {}
    id_manager.add_collection(data)
    assert not id_manager.has_id("some_id")
    data["some_id"] = 1
    assert id_manager.has_id("some_id")
    assert id_manager.generate_id("some_id") == "some_id_2"
    assert id_manager.generate_id("bla") == "bla"


async def test_observable_collection() -> None:
    """Test observerable collection."""
    coll = collection.ObservableCollection(None)
    assert coll.async_items() == []
    coll.data["bla"] = 1
    assert coll.async_items() == [1]

    changes = track_changes(coll)
    await coll.notify_changes(
        [collection.CollectionChangeSet("mock_type", "mock_id", {"mock": "item"})]
    )
    assert len(changes) == 1
    assert changes[0] == ("mock_type", "mock_id", {"mock": "item"})


async def test_yaml_collection() -> None:
    """Test a YAML collection."""
    id_manager = collection.IDManager()
    coll = collection.YamlCollection(_LOGGER, id_manager)
    changes = track_changes(coll)
    await coll.async_load(
        [{"id": "mock-1", "name": "Mock 1"}, {"id": "mock-2", "name": "Mock 2"}]
    )
    assert id_manager.has_id("mock-1")
    assert id_manager.has_id("mock-2")
    assert len(changes) == 2
    assert changes[0] == (
        collection.CHANGE_ADDED,
        "mock-1",
        {"id": "mock-1", "name": "Mock 1"},
    )
    assert changes[1] == (
        collection.CHANGE_ADDED,
        "mock-2",
        {"id": "mock-2", "name": "Mock 2"},
    )

    # Test loading new data. Mock 1 is updated, 2 removed, 3 added.
    await coll.async_load(
        [{"id": "mock-1", "name": "Mock 1-updated"}, {"id": "mock-3", "name": "Mock 3"}]
    )
    assert len(changes) == 5
    assert changes[2] == (
        collection.CHANGE_UPDATED,
        "mock-1",
        {"id": "mock-1", "name": "Mock 1-updated"},
    )
    assert changes[3] == (
        collection.CHANGE_ADDED,
        "mock-3",
        {"id": "mock-3", "name": "Mock 3"},
    )
    assert changes[4] == (
        collection.CHANGE_REMOVED,
        "mock-2",
        {"id": "mock-2", "name": "Mock 2"},
    )


async def test_yaml_collection_skipping_duplicate_ids() -> None:
    """Test YAML collection skipping duplicate IDs."""
    id_manager = collection.IDManager()
    id_manager.add_collection({"existing": True})
    coll = collection.YamlCollection(_LOGGER, id_manager)
    changes = track_changes(coll)
    await coll.async_load(
        [{"id": "mock-1", "name": "Mock 1"}, {"id": "existing", "name": "Mock 2"}]
    )
    assert len(changes) == 1
    assert changes[0] == (
        collection.CHANGE_ADDED,
        "mock-1",
        {"id": "mock-1", "name": "Mock 1"},
    )


async def test_storage_collection(hass: HomeAssistant) -> None:
    """Test storage collection."""
    store = storage.Store(hass, 1, "test-data")
    await store.async_save(
        {
            "items": [
                {"id": "mock-1", "name": "Mock 1", "data": 1},
                {"id": "mock-2", "name": "Mock 2", "data": 2},
            ]
        }
    )
    id_manager = collection.IDManager()
    coll = MockStorageCollection(store, id_manager)
    changes = track_changes(coll)

    await coll.async_load()
    assert id_manager.has_id("mock-1")
    assert id_manager.has_id("mock-2")
    assert len(changes) == 2
    assert changes[0] == (
        collection.CHANGE_ADDED,
        "mock-1",
        {"id": "mock-1", "name": "Mock 1", "data": 1},
    )
    assert changes[1] == (
        collection.CHANGE_ADDED,
        "mock-2",
        {"id": "mock-2", "name": "Mock 2", "data": 2},
    )

    item = await coll.async_create_item({"name": "Mock 3"})
    assert item["id"] == "mock_3"
    assert len(changes) == 3
    assert changes[2] == (
        collection.CHANGE_ADDED,
        "mock_3",
        {"id": "mock_3", "name": "Mock 3"},
    )

    updated_item = await coll.async_update_item("mock-2", {"name": "Mock 2 updated"})
    assert id_manager.has_id("mock-2")
    assert updated_item == {"id": "mock-2", "name": "Mock 2 updated", "data": 2}
    assert len(changes) == 4
    assert changes[3] == (collection.CHANGE_UPDATED, "mock-2", updated_item)

    with pytest.raises(ValueError):
        await coll.async_update_item("mock-2", {"id": "mock-2-updated"})

    assert id_manager.has_id("mock-2")
    assert not id_manager.has_id("mock-2-updated")
    assert len(changes) == 4

    await flush_store(store)

    assert await storage.Store(hass, 1, "test-data").async_load() == {
        "items": [
            {"id": "mock-1", "name": "Mock 1", "data": 1},
            {"id": "mock-2", "name": "Mock 2 updated", "data": 2},
            {"id": "mock_3", "name": "Mock 3"},
        ]
    }


async def test_attach_entity_component_collection(hass: HomeAssistant) -> None:
    """Test attaching collection to entity component."""
    ent_comp = entity_component.EntityComponent(_LOGGER, "test", hass)
    await ent_comp.async_setup({})
    coll = MockObservableCollection(None)
    collection.sync_entity_lifecycle(hass, "test", "test", ent_comp, coll, MockEntity)

    await coll.notify_changes(
        [
            collection.CollectionChangeSet(
                collection.CHANGE_ADDED,
                "mock_id",
                {"id": "mock_id", "state": "initial", "name": "Mock 1"},
            )
        ],
    )

    assert hass.states.get("test.mock_1").name == "Mock 1"
    assert hass.states.get("test.mock_1").state == "initial"

    await coll.notify_changes(
        [
            collection.CollectionChangeSet(
                collection.CHANGE_UPDATED,
                "mock_id",
                {"id": "mock_id", "state": "second", "name": "Mock 1 updated"},
            )
        ],
    )

    assert hass.states.get("test.mock_1").name == "Mock 1 updated"
    assert hass.states.get("test.mock_1").state == "second"

    await coll.notify_changes(
        [collection.CollectionChangeSet(collection.CHANGE_REMOVED, "mock_id", None)],
    )

    assert hass.states.get("test.mock_1") is None


async def test_entity_component_collection_abort(hass: HomeAssistant) -> None:
    """Test aborted entity adding is handled."""
    ent_comp = entity_component.EntityComponent(_LOGGER, "test", hass)
    await ent_comp.async_setup({})
    coll = MockObservableCollection(None)

    async_update_config_calls = []
    async_remove_calls = []

    class MockMockEntity(MockEntity):
        """Track calls to async_update_config and async_remove."""

        async def async_update_config(self, config):
            nonlocal async_update_config_calls
            async_update_config_calls.append(None)
            await super().async_update_config()

        async def async_remove(self, *, force_remove: bool = False):
            nonlocal async_remove_calls
            async_remove_calls.append(None)
            await super().async_remove()

    collection.sync_entity_lifecycle(
        hass, "test", "test", ent_comp, coll, MockMockEntity
    )
    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "test",
        "test",
        "mock_id",
        suggested_object_id="mock_1",
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    await coll.notify_changes(
        [
            collection.CollectionChangeSet(
                collection.CHANGE_ADDED,
                "mock_id",
                {"id": "mock_id", "state": "initial", "name": "Mock 1"},
            )
        ],
    )

    assert hass.states.get("test.mock_1") is None

    await coll.notify_changes(
        [
            collection.CollectionChangeSet(
                collection.CHANGE_UPDATED,
                "mock_id",
                {"id": "mock_id", "state": "second", "name": "Mock 1 updated"},
            )
        ],
    )

    assert hass.states.get("test.mock_1") is None
    assert len(async_update_config_calls) == 0

    await coll.notify_changes(
        [collection.CollectionChangeSet(collection.CHANGE_REMOVED, "mock_id", None)],
    )

    assert hass.states.get("test.mock_1") is None
    assert len(async_remove_calls) == 0


async def test_entity_component_collection_entity_removed(hass: HomeAssistant) -> None:
    """Test entity removal is handled."""
    ent_comp = entity_component.EntityComponent(_LOGGER, "test", hass)
    await ent_comp.async_setup({})
    coll = MockObservableCollection(None)

    async_update_config_calls = []
    async_remove_calls = []

    class MockMockEntity(MockEntity):
        """Track calls to async_update_config and async_remove."""

        async def async_update_config(self, config):
            nonlocal async_update_config_calls
            async_update_config_calls.append(None)
            await super().async_update_config()

        async def async_remove(self, *, force_remove: bool = False):
            nonlocal async_remove_calls
            async_remove_calls.append(None)
            await super().async_remove()

    collection.sync_entity_lifecycle(
        hass, "test", "test", ent_comp, coll, MockMockEntity
    )
    entity_registry = er.async_get(hass)
    entity_registry.async_get_or_create(
        "test", "test", "mock_id", suggested_object_id="mock_1"
    )

    await coll.notify_changes(
        [
            collection.CollectionChangeSet(
                collection.CHANGE_ADDED,
                "mock_id",
                {"id": "mock_id", "state": "initial", "name": "Mock 1"},
            )
        ],
    )

    assert hass.states.get("test.mock_1").name == "Mock 1"
    assert hass.states.get("test.mock_1").state == "initial"

    entity_registry.async_remove("test.mock_1")
    await hass.async_block_till_done()
    assert hass.states.get("test.mock_1") is None
    assert len(async_remove_calls) == 1

    await coll.notify_changes(
        [
            collection.CollectionChangeSet(
                collection.CHANGE_UPDATED,
                "mock_id",
                {"id": "mock_id", "state": "second", "name": "Mock 1 updated"},
            )
        ],
    )

    assert hass.states.get("test.mock_1") is None
    assert len(async_update_config_calls) == 0

    await coll.notify_changes(
        [collection.CollectionChangeSet(collection.CHANGE_REMOVED, "mock_id", None)],
    )

    assert hass.states.get("test.mock_1") is None
    assert len(async_remove_calls) == 1


async def test_storage_collection_websocket(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test exposing a storage collection via websockets."""
    store = storage.Store(hass, 1, "test-data")
    coll = MockStorageCollection(store)
    changes = track_changes(coll)
    collection.DictStorageCollectionWebsocket(
        coll,
        "test_item/collection",
        "test_item",
        {vol.Required("name"): str, vol.Required("immutable_string"): str},
        {vol.Optional("name"): str},
    ).async_setup(hass)

    client = await hass_ws_client(hass)

    # Create invalid
    await client.send_json(
        {
            "id": 1,
            "type": "test_item/collection/create",
            "name": 1,
            # Forgot to add immutable_string
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"
    assert len(changes) == 0

    # Create
    await client.send_json(
        {
            "id": 2,
            "type": "test_item/collection/create",
            "name": "Initial Name",
            "immutable_string": "no-changes",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "id": "initial_name",
        "name": "Initial Name",
        "immutable_string": "no-changes",
    }
    assert len(changes) == 1
    assert changes[0] == (collection.CHANGE_ADDED, "initial_name", response["result"])

    # List
    await client.send_json({"id": 3, "type": "test_item/collection/list"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == [
        {
            "id": "initial_name",
            "name": "Initial Name",
            "immutable_string": "no-changes",
        }
    ]
    assert len(changes) == 1

    # Update invalid data
    await client.send_json(
        {
            "id": 4,
            "type": "test_item/collection/update",
            "test_item_id": "initial_name",
            "immutable_string": "no-changes",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"
    assert len(changes) == 1

    # Update invalid item
    await client.send_json(
        {
            "id": 5,
            "type": "test_item/collection/update",
            "test_item_id": "non-existing",
            "name": "Updated name",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "not_found"
    assert len(changes) == 1

    # Update
    await client.send_json(
        {
            "id": 6,
            "type": "test_item/collection/update",
            "test_item_id": "initial_name",
            "name": "Updated name",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "id": "initial_name",
        "name": "Updated name",
        "immutable_string": "no-changes",
    }
    assert len(changes) == 2
    assert changes[1] == (collection.CHANGE_UPDATED, "initial_name", response["result"])

    # Delete invalid ID
    await client.send_json(
        {"id": 7, "type": "test_item/collection/update", "test_item_id": "non-existing"}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "not_found"
    assert len(changes) == 2

    # Delete
    await client.send_json(
        {"id": 8, "type": "test_item/collection/delete", "test_item_id": "initial_name"}
    )
    response = await client.receive_json()
    assert response["success"]

    assert len(changes) == 3
    assert changes[2] == (
        collection.CHANGE_REMOVED,
        "initial_name",
        {
            "id": "initial_name",
            "immutable_string": "no-changes",
            "name": "Updated name",
        },
    )
