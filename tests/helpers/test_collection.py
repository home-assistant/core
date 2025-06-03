"""Tests for the collection helper."""

from __future__ import annotations

from datetime import timedelta
import logging

from freezegun.api import FrozenDateTimeFactory
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
from homeassistant.util.dt import utcnow

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

    def __init__(self, config: ConfigType) -> None:
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
    def unique_id(self) -> str:
        """Return unique ID of entity."""
        return self._config["id"]

    @property
    def name(self) -> str:
        """Return name of entity."""
        return self._config["name"]

    @property
    def state(self) -> str:
        """Return state of entity."""
        return self._config["state"]

    async def async_update_config(self, config: ConfigType) -> None:
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
        [collection.CollectionChange("mock_type", "mock_id", {"mock": "item"})]
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


async def test_storage_collection_update_modifiet_at(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that updating a storage collection will update the modified_at datetime in the entity registry."""

    entities: dict[str, TestEntity] = {}

    class TestEntity(MockEntity):
        """Entity that is config based."""

        def __init__(self, config: ConfigType) -> None:
            """Initialize entity."""
            super().__init__(config)
            self._state = "initial"

        @classmethod
        def from_storage(cls, config: ConfigType) -> TestEntity:
            """Create instance from storage."""
            obj = super().from_storage(config)
            entities[obj.unique_id] = obj
            return obj

        @property
        def state(self) -> str:
            """Return state of entity."""
            return self._state

        def set_state(self, value: str) -> None:
            """Set value."""
            self._state = value
            self.async_write_ha_state()

    store = storage.Store(hass, 1, "test-data")
    data = {"id": "mock-1", "name": "Mock 1", "data": 1}
    await store.async_save(
        {
            "items": [
                data,
            ]
        }
    )
    id_manager = collection.IDManager()
    ent_comp = entity_component.EntityComponent(_LOGGER, "test", hass)
    await ent_comp.async_setup({})
    coll = MockStorageCollection(store, id_manager)
    collection.sync_entity_lifecycle(hass, "test", "test", ent_comp, coll, TestEntity)
    changes = track_changes(coll)

    await coll.async_load()
    assert id_manager.has_id("mock-1")
    assert len(changes) == 1
    assert changes[0] == (collection.CHANGE_ADDED, "mock-1", data)

    modified_1 = entity_registry.async_get("test.mock_1").modified_at
    assert modified_1 == utcnow()

    freezer.tick(timedelta(minutes=1))

    updated_item = await coll.async_update_item("mock-1", {"data": 2})
    assert id_manager.has_id("mock-1")
    assert updated_item == {"id": "mock-1", "name": "Mock 1", "data": 2}
    assert len(changes) == 2
    assert changes[1] == (collection.CHANGE_UPDATED, "mock-1", updated_item)

    modified_2 = entity_registry.async_get("test.mock_1").modified_at
    assert modified_2 > modified_1
    assert modified_2 == utcnow()

    freezer.tick(timedelta(minutes=1))

    entities["mock-1"].set_state("second")

    modified_3 = entity_registry.async_get("test.mock_1").modified_at
    assert modified_3 == modified_2


async def test_attach_entity_component_collection(hass: HomeAssistant) -> None:
    """Test attaching collection to entity component."""
    ent_comp = entity_component.EntityComponent(_LOGGER, "test", hass)
    await ent_comp.async_setup({})
    coll = MockObservableCollection(None)
    collection.sync_entity_lifecycle(hass, "test", "test", ent_comp, coll, MockEntity)

    await coll.notify_changes(
        [
            collection.CollectionChange(
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
            collection.CollectionChange(
                collection.CHANGE_UPDATED,
                "mock_id",
                {"id": "mock_id", "state": "second", "name": "Mock 1 updated"},
            )
        ],
    )

    assert hass.states.get("test.mock_1").name == "Mock 1 updated"
    assert hass.states.get("test.mock_1").state == "second"

    await coll.notify_changes(
        [collection.CollectionChange(collection.CHANGE_REMOVED, "mock_id", None)],
    )

    assert hass.states.get("test.mock_1") is None


async def test_entity_component_collection_abort(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
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
    entity_registry.async_get_or_create(
        "test",
        "test",
        "mock_id",
        suggested_object_id="mock_1",
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    await coll.notify_changes(
        [
            collection.CollectionChange(
                collection.CHANGE_ADDED,
                "mock_id",
                {"id": "mock_id", "state": "initial", "name": "Mock 1"},
            )
        ],
    )

    assert hass.states.get("test.mock_1") is None

    await coll.notify_changes(
        [
            collection.CollectionChange(
                collection.CHANGE_UPDATED,
                "mock_id",
                {"id": "mock_id", "state": "second", "name": "Mock 1 updated"},
            )
        ],
    )

    assert hass.states.get("test.mock_1") is None
    assert len(async_update_config_calls) == 0

    await coll.notify_changes(
        [collection.CollectionChange(collection.CHANGE_REMOVED, "mock_id", None)],
    )

    assert hass.states.get("test.mock_1") is None
    assert len(async_remove_calls) == 0


async def test_entity_component_collection_entity_removed(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
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
    entity_registry.async_get_or_create(
        "test", "test", "mock_id", suggested_object_id="mock_1"
    )

    await coll.notify_changes(
        [
            collection.CollectionChange(
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
            collection.CollectionChange(
                collection.CHANGE_UPDATED,
                "mock_id",
                {"id": "mock_id", "state": "second", "name": "Mock 1 updated"},
            )
        ],
    )

    assert hass.states.get("test.mock_1") is None
    assert len(async_update_config_calls) == 0

    await coll.notify_changes(
        [collection.CollectionChange(collection.CHANGE_REMOVED, "mock_id", None)],
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id({"type": "test_item/collection/list"})
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {"type": "test_item/collection/update", "test_item_id": "non-existing"}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "not_found"
    assert len(changes) == 2

    # Delete
    await client.send_json_auto_id(
        {"type": "test_item/collection/delete", "test_item_id": "initial_name"}
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


async def test_storage_collection_websocket_subscribe(
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

    # Subscribe
    await client.send_json_auto_id({"type": "test_item/collection/subscribe"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None
    assert len(changes) == 0
    event_id = response["id"]

    response = await client.receive_json()
    assert response["id"] == event_id
    assert response["event"] == []

    # Create invalid
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
            "type": "test_item/collection/create",
            "name": "Initial Name",
            "immutable_string": "no-changes",
        }
    )
    response = await client.receive_json()
    assert response["id"] == event_id
    assert response["event"] == [
        {
            "change_type": "added",
            "item": {
                "id": "initial_name",
                "immutable_string": "no-changes",
                "name": "Initial Name",
            },
            "test_item_id": "initial_name",
        }
    ]
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        "id": "initial_name",
        "name": "Initial Name",
        "immutable_string": "no-changes",
    }
    assert len(changes) == 1
    assert changes[0] == (collection.CHANGE_ADDED, "initial_name", response["result"])

    # Subscribe again
    await client.send_json_auto_id({"type": "test_item/collection/subscribe"})
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] is None
    event_id_2 = response["id"]

    response = await client.receive_json()
    assert response["id"] == event_id_2
    assert response["event"] == [
        {
            "change_type": "added",
            "item": {
                "id": "initial_name",
                "immutable_string": "no-changes",
                "name": "Initial Name",
            },
            "test_item_id": "initial_name",
        },
    ]

    await client.send_json_auto_id(
        {"type": "unsubscribe_events", "subscription": event_id_2}
    )
    response = await client.receive_json()
    assert response["success"]

    # List
    await client.send_json_auto_id({"type": "test_item/collection/list"})
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
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
    await client.send_json_auto_id(
        {
            "type": "test_item/collection/update",
            "test_item_id": "initial_name",
            "name": "Updated name",
        }
    )
    response = await client.receive_json()
    assert response["id"] == event_id
    assert response["event"] == [
        {
            "change_type": "updated",
            "item": {
                "id": "initial_name",
                "immutable_string": "no-changes",
                "name": "Updated name",
            },
            "test_item_id": "initial_name",
        }
    ]
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
    await client.send_json_auto_id(
        {"type": "test_item/collection/update", "test_item_id": "non-existing"}
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "not_found"
    assert len(changes) == 2

    # Delete
    await client.send_json_auto_id(
        {"type": "test_item/collection/delete", "test_item_id": "initial_name"}
    )
    response = await client.receive_json()
    assert response["id"] == event_id
    assert response["event"] == [
        {
            "change_type": "removed",
            "item": {
                "id": "initial_name",
                "immutable_string": "no-changes",
                "name": "Updated name",
            },
            "test_item_id": "initial_name",
        }
    ]
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
