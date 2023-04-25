"""Test Home Assistant exposed entities helper."""
import pytest

from homeassistant.components.homeassistant.exposed_entities import (
    DATA_EXPOSED_ENTITIES,
    ExposedEntities,
    async_get_assistant_settings,
    async_listen_entity_updates,
    async_should_expose,
)
from homeassistant.const import CLOUD_NEVER_EXPOSED_ENTITIES, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import flush_store
from tests.typing import WebSocketGenerator


async def test_load_preferences(hass: HomeAssistant) -> None:
    """Make sure that we can load/save data correctly."""
    assert await async_setup_component(hass, "homeassistant", {})

    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    assert exposed_entities._assistants == {}

    exposed_entities.async_set_expose_new_entities("test1", True)
    exposed_entities.async_set_expose_new_entities("test2", False)

    assert list(exposed_entities._assistants) == ["test1", "test2"]

    exposed_entities2 = ExposedEntities(hass)
    await flush_store(exposed_entities._store)
    await exposed_entities2.async_load()

    assert exposed_entities._assistants == exposed_entities2._assistants


async def test_expose_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test expose entity."""
    ws_client = await hass_ws_client(hass)
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    entry1 = entity_registry.async_get_or_create("test", "test", "unique1")
    entry2 = entity_registry.async_get_or_create("test", "test", "unique2")

    # Set options
    await ws_client.send_json_auto_id(
        {
            "type": "homeassistant/expose_entity",
            "assistants": ["cloud.alexa"],
            "entity_ids": [entry1.entity_id],
            "should_expose": True,
        }
    )

    response = await ws_client.receive_json()
    assert response["success"]

    entry1 = entity_registry.async_get(entry1.entity_id)
    assert entry1.options == {"cloud.alexa": {"should_expose": True}}
    entry2 = entity_registry.async_get(entry2.entity_id)
    assert entry2.options == {}

    # Update options
    await ws_client.send_json_auto_id(
        {
            "type": "homeassistant/expose_entity",
            "assistants": ["cloud.alexa", "cloud.google_assistant"],
            "entity_ids": [entry1.entity_id, entry2.entity_id],
            "should_expose": False,
        }
    )

    response = await ws_client.receive_json()
    assert response["success"]

    entry1 = entity_registry.async_get(entry1.entity_id)
    assert entry1.options == {
        "cloud.alexa": {"should_expose": False},
        "cloud.google_assistant": {"should_expose": False},
    }
    entry2 = entity_registry.async_get(entry2.entity_id)
    assert entry2.options == {
        "cloud.alexa": {"should_expose": False},
        "cloud.google_assistant": {"should_expose": False},
    }


async def test_expose_entity_unknown(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test behavior when exposing an unknown entity."""
    ws_client = await hass_ws_client(hass)
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]

    # Set options
    await ws_client.send_json_auto_id(
        {
            "type": "homeassistant/expose_entity",
            "assistants": ["cloud.alexa"],
            "entity_ids": ["test.test"],
            "should_expose": True,
        }
    )

    response = await ws_client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "not_found",
        "message": "can't expose 'test.test'",
    }

    with pytest.raises(HomeAssistantError):
        exposed_entities.async_expose_entity("cloud.alexa", "test.test", True)


async def test_expose_entity_blocked(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test behavior when exposing a blocked entity."""
    ws_client = await hass_ws_client(hass)
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    # Set options
    await ws_client.send_json_auto_id(
        {
            "type": "homeassistant/expose_entity",
            "assistants": ["cloud.alexa"],
            "entity_ids": ["group.all_locks"],
            "should_expose": True,
        }
    )

    response = await ws_client.receive_json()
    assert not response["success"]
    assert response["error"] == {
        "code": "not_allowed",
        "message": "can't expose 'group.all_locks'",
    }


@pytest.mark.parametrize("expose_new", [True, False])
async def test_expose_new_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    expose_new,
) -> None:
    """Test expose entity."""
    ws_client = await hass_ws_client(hass)
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    entry1 = entity_registry.async_get_or_create("climate", "test", "unique1")
    entry2 = entity_registry.async_get_or_create("climate", "test", "unique2")

    await ws_client.send_json_auto_id(
        {
            "type": "homeassistant/expose_new_entities/get",
            "assistant": "cloud.alexa",
        }
    )
    response = await ws_client.receive_json()
    assert response["success"]
    assert response["result"] == {"expose_new": False}

    # Check if exposed - should be False
    assert async_should_expose(hass, "cloud.alexa", entry1.entity_id) is False

    # Expose new entities to Alexa
    await ws_client.send_json_auto_id(
        {
            "type": "homeassistant/expose_new_entities/set",
            "assistant": "cloud.alexa",
            "expose_new": expose_new,
        }
    )
    response = await ws_client.receive_json()
    assert response["success"]
    await ws_client.send_json_auto_id(
        {
            "type": "homeassistant/expose_new_entities/get",
            "assistant": "cloud.alexa",
        }
    )
    response = await ws_client.receive_json()
    assert response["success"]
    assert response["result"] == {"expose_new": expose_new}

    # Check again if exposed - should still be False
    assert async_should_expose(hass, "cloud.alexa", entry1.entity_id) is False

    # Check if exposed - should be True
    assert async_should_expose(hass, "cloud.alexa", entry2.entity_id) == expose_new


async def test_listen_updates(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test listen to updates."""
    calls = []

    def listener():
        calls.append(None)

    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]
    async_listen_entity_updates(hass, "cloud.alexa", listener)

    entry = entity_registry.async_get_or_create("climate", "test", "unique1")

    # Call for another assistant - listener not called
    exposed_entities.async_expose_entity(
        "cloud.google_assistant", entry.entity_id, True
    )
    assert len(calls) == 0

    # Call for our assistant - listener called
    exposed_entities.async_expose_entity("cloud.alexa", entry.entity_id, True)
    assert len(calls) == 1

    # Settings not changed - listener not called
    exposed_entities.async_expose_entity("cloud.alexa", entry.entity_id, True)
    assert len(calls) == 1

    # Settings changed - listener called
    exposed_entities.async_expose_entity("cloud.alexa", entry.entity_id, False)
    assert len(calls) == 2


async def test_get_assistant_settings(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test get assistant settings."""
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    exposed_entities: ExposedEntities = hass.data[DATA_EXPOSED_ENTITIES]

    entry = entity_registry.async_get_or_create("climate", "test", "unique1")

    assert async_get_assistant_settings(hass, "cloud.alexa") == {}

    exposed_entities.async_expose_entity("cloud.alexa", entry.entity_id, True)
    assert async_get_assistant_settings(hass, "cloud.alexa") == {
        "climate.test_unique1": {"should_expose": True}
    }
    assert async_get_assistant_settings(hass, "cloud.google_assistant") == {}


async def test_should_expose(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test expose entity."""
    ws_client = await hass_ws_client(hass)
    assert await async_setup_component(hass, "homeassistant", {})
    await hass.async_block_till_done()

    # Expose new entities to Alexa
    await ws_client.send_json_auto_id(
        {
            "type": "homeassistant/expose_new_entities/set",
            "assistant": "cloud.alexa",
            "expose_new": True,
        }
    )
    response = await ws_client.receive_json()
    assert response["success"]

    # Unknown entity is not exposed
    assert async_should_expose(hass, "test.test", "test.test") is False

    # Blocked entity is not exposed
    entry_blocked = entity_registry.async_get_or_create(
        "group", "test", "unique", suggested_object_id="all_locks"
    )
    assert entry_blocked.entity_id == CLOUD_NEVER_EXPOSED_ENTITIES[0]
    assert async_should_expose(hass, "cloud.alexa", entry_blocked.entity_id) is False

    # Lock is exposed
    lock1 = entity_registry.async_get_or_create("lock", "test", "unique1")
    assert entry_blocked.entity_id == CLOUD_NEVER_EXPOSED_ENTITIES[0]
    assert async_should_expose(hass, "cloud.alexa", lock1.entity_id) is True

    # Hidden entity is not exposed
    lock2 = entity_registry.async_get_or_create(
        "lock", "test", "unique2", hidden_by=er.RegistryEntryHider.USER
    )
    assert entry_blocked.entity_id == CLOUD_NEVER_EXPOSED_ENTITIES[0]
    assert async_should_expose(hass, "cloud.alexa", lock2.entity_id) is False

    # Entity with category is not exposed
    lock3 = entity_registry.async_get_or_create(
        "lock", "test", "unique3", entity_category=EntityCategory.CONFIG
    )
    assert entry_blocked.entity_id == CLOUD_NEVER_EXPOSED_ENTITIES[0]
    assert async_should_expose(hass, "cloud.alexa", lock3.entity_id) is False

    # Binary sensor without device class is not exposed
    binarysensor1 = entity_registry.async_get_or_create(
        "binary_sensor", "test", "unique1"
    )
    assert entry_blocked.entity_id == CLOUD_NEVER_EXPOSED_ENTITIES[0]
    assert async_should_expose(hass, "cloud.alexa", binarysensor1.entity_id) is False

    # Binary sensor with certain device class is exposed
    binarysensor2 = entity_registry.async_get_or_create(
        "binary_sensor",
        "test",
        "unique2",
        original_device_class="door",
    )
    assert entry_blocked.entity_id == CLOUD_NEVER_EXPOSED_ENTITIES[0]
    assert async_should_expose(hass, "cloud.alexa", binarysensor2.entity_id) is True

    # Sensor without device class is not exposed
    sensor1 = entity_registry.async_get_or_create("sensor", "test", "unique1")
    assert entry_blocked.entity_id == CLOUD_NEVER_EXPOSED_ENTITIES[0]
    assert async_should_expose(hass, "cloud.alexa", sensor1.entity_id) is False

    # Sensor with certain device class is exposed
    sensor2 = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique2",
        original_device_class="temperature",
    )
    assert entry_blocked.entity_id == CLOUD_NEVER_EXPOSED_ENTITIES[0]
    assert async_should_expose(hass, "cloud.alexa", sensor2.entity_id) is True
