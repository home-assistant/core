"""Tests for the collection helper."""
import logging

import pytest
import voluptuous as vol

from homeassistant.helpers import collection, entity, entity_component, storage

from tests.common import flush_store

LOGGER = logging.getLogger(__name__)


def track_changes(coll: collection.ObservableCollection):
    """Create helper to track changes in a collection."""
    changes = []

    async def listener(*args):
        changes.append(args)

    coll.async_add_listener(listener)

    return changes


class MockEntity(entity.Entity):
    """Entity that is config based."""

    def __init__(self, config):
        """Initialize entity."""
        self._config = config

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


class MockStorageCollection(collection.StorageCollection):
    """Mock storage collection."""

    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        if "name" not in data:
            raise ValueError("invalid")

        return data

    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return info["name"]

    async def _update_data(self, data: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        return {**data, **update_data}


def test_id_manager():
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


async def test_observable_collection():
    """Test observerable collection."""
    coll = collection.ObservableCollection(LOGGER)
    assert coll.async_items() == []
    coll.data["bla"] = 1
    assert coll.async_items() == [1]

    changes = track_changes(coll)
    await coll.notify_change("mock_type", "mock_id", {"mock": "item"})
    assert len(changes) == 1
    assert changes[0] == ("mock_type", "mock_id", {"mock": "item"})


async def test_yaml_collection():
    """Test a YAML collection."""
    id_manager = collection.IDManager()
    coll = collection.YamlCollection(LOGGER, id_manager)
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


async def test_yaml_collection_skipping_duplicate_ids():
    """Test YAML collection skipping duplicate IDs."""
    id_manager = collection.IDManager()
    id_manager.add_collection({"existing": True})
    coll = collection.YamlCollection(LOGGER, id_manager)
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


async def test_storage_collection(hass):
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
    coll = MockStorageCollection(store, LOGGER, id_manager)
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


async def test_attach_entity_component_collection(hass):
    """Test attaching collection to entity component."""
    ent_comp = entity_component.EntityComponent(LOGGER, "test", hass)
    coll = collection.ObservableCollection(LOGGER)
    collection.attach_entity_component_collection(ent_comp, coll, MockEntity)

    await coll.notify_change(
        collection.CHANGE_ADDED,
        "mock_id",
        {"id": "mock_id", "state": "initial", "name": "Mock 1"},
    )

    assert hass.states.get("test.mock_1").name == "Mock 1"
    assert hass.states.get("test.mock_1").state == "initial"

    await coll.notify_change(
        collection.CHANGE_UPDATED,
        "mock_id",
        {"id": "mock_id", "state": "second", "name": "Mock 1 updated"},
    )

    assert hass.states.get("test.mock_1").name == "Mock 1 updated"
    assert hass.states.get("test.mock_1").state == "second"

    await coll.notify_change(collection.CHANGE_REMOVED, "mock_id", None)

    assert hass.states.get("test.mock_1") is None


async def test_storage_collection_websocket(hass, hass_ws_client):
    """Test exposing a storage collection via websockets."""
    store = storage.Store(hass, 1, "test-data")
    coll = MockStorageCollection(store, LOGGER)
    changes = track_changes(coll)
    collection.StorageCollectionWebsocket(
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
