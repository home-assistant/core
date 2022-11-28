"""Test entity_registry API."""
from unittest.mock import ANY

import pytest

from homeassistant.components.config import entity_registry
from homeassistant.const import ATTR_ICON
from homeassistant.helpers.device_registry import DeviceEntryDisabler
from homeassistant.helpers.entity_registry import (
    EVENT_ENTITY_REGISTRY_UPDATED,
    RegistryEntry,
    RegistryEntryDisabler,
    RegistryEntryHider,
    async_get as async_get_entity_registry,
)

from tests.common import (
    MockConfigEntry,
    MockEntity,
    MockEntityPlatform,
    mock_device_registry,
    mock_registry,
)


@pytest.fixture
def client(hass, hass_ws_client):
    """Fixture that can interact with the config manager API."""
    hass.loop.run_until_complete(entity_registry.async_setup(hass))
    yield hass.loop.run_until_complete(hass_ws_client(hass))


@pytest.fixture
def device_registry(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


async def test_list_entities(hass, client):
    """Test list entries."""
    mock_registry(
        hass,
        {
            "test_domain.name": RegistryEntry(
                entity_id="test_domain.name",
                unique_id="1234",
                platform="test_platform",
                name="Hello World",
            ),
            "test_domain.no_name": RegistryEntry(
                entity_id="test_domain.no_name",
                unique_id="6789",
                platform="test_platform",
            ),
        },
    )

    await client.send_json({"id": 5, "type": "config/entity_registry/list"})
    msg = await client.receive_json()

    assert msg["result"] == [
        {
            "area_id": None,
            "config_entry_id": None,
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.name",
            "has_entity_name": False,
            "hidden_by": None,
            "icon": None,
            "id": ANY,
            "name": "Hello World",
            "original_name": None,
            "platform": "test_platform",
        },
        {
            "area_id": None,
            "config_entry_id": None,
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.no_name",
            "has_entity_name": False,
            "hidden_by": None,
            "icon": None,
            "id": ANY,
            "name": None,
            "original_name": None,
            "platform": "test_platform",
        },
    ]

    mock_registry(
        hass,
        {
            "test_domain.name": RegistryEntry(
                entity_id="test_domain.name",
                unique_id="1234",
                platform="test_platform",
                name="Hello World",
            ),
        },
    )

    hass.bus.async_fire(
        EVENT_ENTITY_REGISTRY_UPDATED,
        {"action": "create", "entity_id": "test_domain.no_name"},
    )
    await client.send_json({"id": 6, "type": "config/entity_registry/list"})
    msg = await client.receive_json()

    assert msg["result"] == [
        {
            "area_id": None,
            "config_entry_id": None,
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.name",
            "has_entity_name": False,
            "hidden_by": None,
            "icon": None,
            "id": ANY,
            "name": "Hello World",
            "original_name": None,
            "platform": "test_platform",
        },
    ]


async def test_get_entity(hass, client):
    """Test get entry."""
    mock_registry(
        hass,
        {
            "test_domain.name": RegistryEntry(
                entity_id="test_domain.name",
                unique_id="1234",
                platform="test_platform",
                name="Hello World",
            ),
            "test_domain.no_name": RegistryEntry(
                entity_id="test_domain.no_name",
                unique_id="6789",
                platform="test_platform",
            ),
        },
    )

    await client.send_json(
        {"id": 5, "type": "config/entity_registry/get", "entity_id": "test_domain.name"}
    )
    msg = await client.receive_json()

    assert msg["result"] == {
        "area_id": None,
        "capabilities": None,
        "config_entry_id": None,
        "device_class": None,
        "device_id": None,
        "disabled_by": None,
        "entity_category": None,
        "entity_id": "test_domain.name",
        "hidden_by": None,
        "icon": None,
        "id": ANY,
        "has_entity_name": False,
        "name": "Hello World",
        "options": {},
        "original_device_class": None,
        "original_icon": None,
        "original_name": None,
        "platform": "test_platform",
        "unique_id": "1234",
    }

    await client.send_json(
        {
            "id": 6,
            "type": "config/entity_registry/get",
            "entity_id": "test_domain.no_name",
        }
    )
    msg = await client.receive_json()

    assert msg["result"] == {
        "area_id": None,
        "capabilities": None,
        "config_entry_id": None,
        "device_class": None,
        "device_id": None,
        "disabled_by": None,
        "entity_category": None,
        "entity_id": "test_domain.no_name",
        "hidden_by": None,
        "icon": None,
        "id": ANY,
        "has_entity_name": False,
        "name": None,
        "options": {},
        "original_device_class": None,
        "original_icon": None,
        "original_name": None,
        "platform": "test_platform",
        "unique_id": "6789",
    }


async def test_update_entity(hass, client):
    """Test updating entity."""
    registry = mock_registry(
        hass,
        {
            "test_domain.world": RegistryEntry(
                entity_id="test_domain.world",
                unique_id="1234",
                # Using component.async_add_entities is equal to platform "domain"
                platform="test_platform",
                name="before update",
                icon="icon:before update",
            )
        },
    )
    platform = MockEntityPlatform(hass)
    entity = MockEntity(unique_id="1234")
    await platform.async_add_entities([entity])

    state = hass.states.get("test_domain.world")
    assert state is not None
    assert state.name == "before update"
    assert state.attributes[ATTR_ICON] == "icon:before update"

    # UPDATE AREA, DEVICE_CLASS, HIDDEN_BY, ICON AND NAME
    await client.send_json(
        {
            "id": 6,
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "area_id": "mock-area-id",
            "device_class": "custom_device_class",
            "hidden_by": "user",  # We exchange strings over the WS API, not enums
            "icon": "icon:after update",
            "name": "after update",
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "entity_entry": {
            "area_id": "mock-area-id",
            "capabilities": None,
            "config_entry_id": None,
            "device_class": "custom_device_class",
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.world",
            "hidden_by": "user",  # We exchange strings over the WS API, not enums
            "icon": "icon:after update",
            "id": ANY,
            "has_entity_name": False,
            "name": "after update",
            "options": {},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "unique_id": "1234",
        }
    }

    state = hass.states.get("test_domain.world")
    assert state.name == "after update"
    assert state.attributes[ATTR_ICON] == "icon:after update"

    # UPDATE HIDDEN_BY TO ILLEGAL VALUE
    await client.send_json(
        {
            "id": 7,
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "hidden_by": "ivy",
        }
    )

    msg = await client.receive_json()
    assert not msg["success"]

    assert registry.entities["test_domain.world"].hidden_by is RegistryEntryHider.USER

    # UPDATE DISABLED_BY TO USER
    await client.send_json(
        {
            "id": 8,
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "disabled_by": "user",  # We exchange strings over the WS API, not enums
        }
    )

    msg = await client.receive_json()
    assert msg["success"]

    assert hass.states.get("test_domain.world") is None
    assert (
        registry.entities["test_domain.world"].disabled_by is RegistryEntryDisabler.USER
    )

    # UPDATE DISABLED_BY TO NONE
    await client.send_json(
        {
            "id": 9,
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "disabled_by": None,
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "entity_entry": {
            "area_id": "mock-area-id",
            "capabilities": None,
            "config_entry_id": None,
            "device_class": "custom_device_class",
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.world",
            "hidden_by": "user",  # We exchange strings over the WS API, not enums
            "icon": "icon:after update",
            "id": ANY,
            "has_entity_name": False,
            "name": "after update",
            "options": {},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "unique_id": "1234",
        },
        "reload_delay": 30,
    }

    # UPDATE ENTITY OPTION
    await client.send_json(
        {
            "id": 10,
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "options_domain": "sensor",
            "options": {"unit_of_measurement": "beard_second"},
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "entity_entry": {
            "area_id": "mock-area-id",
            "capabilities": None,
            "config_entry_id": None,
            "device_class": "custom_device_class",
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.world",
            "hidden_by": "user",  # We exchange strings over the WS API, not enums
            "icon": "icon:after update",
            "id": ANY,
            "has_entity_name": False,
            "name": "after update",
            "options": {"sensor": {"unit_of_measurement": "beard_second"}},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "unique_id": "1234",
        },
    }


async def test_update_entity_require_restart(hass, client):
    """Test updating entity."""
    entity_id = "test_domain.test_platform_1234"
    config_entry = MockConfigEntry(domain="test_platform")
    config_entry.add_to_hass(hass)
    platform = MockEntityPlatform(hass)
    platform.config_entry = config_entry
    entity = MockEntity(unique_id="1234")
    await platform.async_add_entities([entity])

    state = hass.states.get(entity_id)
    assert state is not None

    # UPDATE DISABLED_BY TO NONE
    await client.send_json(
        {
            "id": 8,
            "type": "config/entity_registry/update",
            "entity_id": entity_id,
            "disabled_by": None,
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "entity_entry": {
            "area_id": None,
            "capabilities": None,
            "config_entry_id": config_entry.entry_id,
            "device_class": None,
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": entity_id,
            "icon": None,
            "id": ANY,
            "hidden_by": None,
            "has_entity_name": False,
            "name": None,
            "options": {},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "unique_id": "1234",
        },
        "require_restart": True,
    }


async def test_enable_entity_disabled_device(hass, client, device_registry):
    """Test enabling entity of disabled device."""
    entity_id = "test_domain.test_platform_1234"
    config_entry = MockConfigEntry(domain="test_platform")
    config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id="1234",
        connections={("ethernet", "12:34:56:78:90:AB:CD:EF")},
        identifiers={("bridgeid", "0123")},
        manufacturer="manufacturer",
        model="model",
        disabled_by=DeviceEntryDisabler.USER,
    )
    device_info = {
        "connections": {("ethernet", "12:34:56:78:90:AB:CD:EF")},
    }

    platform = MockEntityPlatform(hass)
    platform.config_entry = config_entry
    entity = MockEntity(unique_id="1234", device_info=device_info)
    await platform.async_add_entities([entity])

    state = hass.states.get(entity_id)
    assert state is None

    entity_reg = async_get_entity_registry(hass)
    entity_entry = entity_reg.async_get(entity_id)
    assert entity_entry.config_entry_id == config_entry.entry_id
    assert entity_entry.device_id == device.id
    assert entity_entry.disabled_by == RegistryEntryDisabler.DEVICE

    # UPDATE DISABLED_BY TO NONE
    await client.send_json(
        {
            "id": 8,
            "type": "config/entity_registry/update",
            "entity_id": entity_id,
            "disabled_by": None,
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]


async def test_update_entity_no_changes(hass, client):
    """Test update entity with no changes."""
    mock_registry(
        hass,
        {
            "test_domain.world": RegistryEntry(
                entity_id="test_domain.world",
                unique_id="1234",
                # Using component.async_add_entities is equal to platform "domain"
                platform="test_platform",
                name="name of entity",
            )
        },
    )
    platform = MockEntityPlatform(hass)
    entity = MockEntity(unique_id="1234")
    await platform.async_add_entities([entity])

    state = hass.states.get("test_domain.world")
    assert state is not None
    assert state.name == "name of entity"

    await client.send_json(
        {
            "id": 6,
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "name": "name of entity",
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "entity_entry": {
            "area_id": None,
            "capabilities": None,
            "config_entry_id": None,
            "device_class": None,
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.world",
            "hidden_by": None,
            "icon": None,
            "id": ANY,
            "has_entity_name": False,
            "name": "name of entity",
            "options": {},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "unique_id": "1234",
        }
    }

    state = hass.states.get("test_domain.world")
    assert state.name == "name of entity"


async def test_get_nonexisting_entity(client):
    """Test get entry with nonexisting entity."""
    await client.send_json(
        {
            "id": 6,
            "type": "config/entity_registry/get",
            "entity_id": "test_domain.no_name",
        }
    )
    msg = await client.receive_json()

    assert not msg["success"]


async def test_update_nonexisting_entity(client):
    """Test update a nonexisting entity."""
    await client.send_json(
        {
            "id": 6,
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.no_name",
            "name": "new-name",
        }
    )
    msg = await client.receive_json()

    assert not msg["success"]


async def test_update_entity_id(hass, client):
    """Test update entity id."""
    mock_registry(
        hass,
        {
            "test_domain.world": RegistryEntry(
                entity_id="test_domain.world",
                unique_id="1234",
                # Using component.async_add_entities is equal to platform "domain"
                platform="test_platform",
            )
        },
    )
    platform = MockEntityPlatform(hass)
    entity = MockEntity(unique_id="1234")
    await platform.async_add_entities([entity])

    assert hass.states.get("test_domain.world") is not None

    await client.send_json(
        {
            "id": 6,
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "new_entity_id": "test_domain.planet",
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "entity_entry": {
            "area_id": None,
            "capabilities": None,
            "config_entry_id": None,
            "device_class": None,
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.planet",
            "hidden_by": None,
            "icon": None,
            "id": ANY,
            "has_entity_name": False,
            "name": None,
            "options": {},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "unique_id": "1234",
        }
    }

    assert hass.states.get("test_domain.world") is None
    assert hass.states.get("test_domain.planet") is not None


async def test_update_existing_entity_id(hass, client):
    """Test update entity id to an already registered entity id."""
    mock_registry(
        hass,
        {
            "test_domain.world": RegistryEntry(
                entity_id="test_domain.world",
                unique_id="1234",
                # Using component.async_add_entities is equal to platform "domain"
                platform="test_platform",
            ),
            "test_domain.planet": RegistryEntry(
                entity_id="test_domain.planet",
                unique_id="2345",
                # Using component.async_add_entities is equal to platform "domain"
                platform="test_platform",
            ),
        },
    )
    platform = MockEntityPlatform(hass)
    entities = [MockEntity(unique_id="1234"), MockEntity(unique_id="2345")]
    await platform.async_add_entities(entities)

    await client.send_json(
        {
            "id": 6,
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "new_entity_id": "test_domain.planet",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]


async def test_update_invalid_entity_id(hass, client):
    """Test update entity id to an invalid entity id."""
    mock_registry(
        hass,
        {
            "test_domain.world": RegistryEntry(
                entity_id="test_domain.world",
                unique_id="1234",
                # Using component.async_add_entities is equal to platform "domain"
                platform="test_platform",
            )
        },
    )
    platform = MockEntityPlatform(hass)
    entities = [MockEntity(unique_id="1234"), MockEntity(unique_id="2345")]
    await platform.async_add_entities(entities)

    await client.send_json(
        {
            "id": 6,
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "new_entity_id": "another_domain.planet",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]


async def test_remove_entity(hass, client):
    """Test removing entity."""
    registry = mock_registry(
        hass,
        {
            "test_domain.world": RegistryEntry(
                entity_id="test_domain.world",
                unique_id="1234",
                # Using component.async_add_entities is equal to platform "domain"
                platform="test_platform",
                name="before update",
            )
        },
    )

    await client.send_json(
        {
            "id": 6,
            "type": "config/entity_registry/remove",
            "entity_id": "test_domain.world",
        }
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert len(registry.entities) == 0


async def test_remove_non_existing_entity(hass, client):
    """Test removing non existing entity."""
    mock_registry(hass, {})

    await client.send_json(
        {
            "id": 6,
            "type": "config/entity_registry/remove",
            "entity_id": "test_domain.world",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
