"""Test entity_registry API."""

from datetime import datetime

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_unordered import unordered

from homeassistant.components.config import entity_registry
from homeassistant.const import ATTR_ICON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryDisabler
from homeassistant.helpers.entity_registry import (
    RegistryEntry,
    RegistryEntryDisabler,
    RegistryEntryHider,
)
from homeassistant.util.dt import utcnow

from tests.common import (
    ANY,
    MockConfigEntry,
    MockEntity,
    MockEntityPlatform,
    mock_registry,
)
from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.fixture
async def client(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> MockHAClientWebSocket:
    """Fixture that can interact with the config manager API."""
    entity_registry.async_setup(hass)
    return await hass_ws_client(hass)


@pytest.mark.usefixtures("freezer")
async def test_list_entities(
    hass: HomeAssistant, client: MockHAClientWebSocket
) -> None:
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

    await client.send_json_auto_id({"type": "config/entity_registry/list"})
    msg = await client.receive_json()

    assert msg["result"] == [
        {
            "area_id": None,
            "categories": {},
            "config_entry_id": None,
            "config_subentry_id": None,
            "created_at": utcnow().timestamp(),
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.name",
            "has_entity_name": False,
            "hidden_by": None,
            "icon": None,
            "id": ANY,
            "labels": [],
            "modified_at": utcnow().timestamp(),
            "name": "Hello World",
            "options": {},
            "original_name": None,
            "platform": "test_platform",
            "translation_key": None,
            "unique_id": ANY,
        },
        {
            "area_id": None,
            "categories": {},
            "config_entry_id": None,
            "config_subentry_id": None,
            "created_at": utcnow().timestamp(),
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.no_name",
            "has_entity_name": False,
            "hidden_by": None,
            "icon": None,
            "id": ANY,
            "labels": [],
            "modified_at": utcnow().timestamp(),
            "name": None,
            "options": {},
            "original_name": None,
            "platform": "test_platform",
            "translation_key": None,
            "unique_id": ANY,
        },
    ]

    class Unserializable:
        """Good luck serializing me."""

    mock_registry(
        hass,
        {
            "test_domain.name": RegistryEntry(
                entity_id="test_domain.name",
                unique_id="1234",
                platform="test_platform",
                name="Hello World",
            ),
            "test_domain.name_2": RegistryEntry(
                entity_id="test_domain.name_2",
                unique_id="6789",
                platform="test_platform",
                name=Unserializable(),
            ),
        },
    )

    await client.send_json_auto_id({"type": "config/entity_registry/list"})
    msg = await client.receive_json()

    assert msg["result"] == [
        {
            "area_id": None,
            "categories": {},
            "config_entry_id": None,
            "config_subentry_id": None,
            "created_at": utcnow().timestamp(),
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.name",
            "has_entity_name": False,
            "hidden_by": None,
            "icon": None,
            "id": ANY,
            "labels": [],
            "modified_at": utcnow().timestamp(),
            "name": "Hello World",
            "options": {},
            "original_name": None,
            "platform": "test_platform",
            "translation_key": None,
            "unique_id": ANY,
        },
    ]


async def test_list_entities_for_display(
    hass: HomeAssistant, client: MockHAClientWebSocket
) -> None:
    """Test list entries."""
    mock_registry(
        hass,
        {
            "test_domain.test": RegistryEntry(
                area_id="area52",
                device_id="device123",
                entity_category=EntityCategory.DIAGNOSTIC,
                entity_id="test_domain.test",
                has_entity_name=True,
                icon="mdi:icon",
                original_name="Hello World",
                platform="test_platform",
                translation_key="translations_galore",
                unique_id="1234",
            ),
            "test_domain.nameless": RegistryEntry(
                area_id="area52",
                device_id="device123",
                entity_id="test_domain.nameless",
                has_entity_name=True,
                icon=None,
                original_name=None,
                platform="test_platform",
                unique_id="2345",
            ),
            "test_domain.renamed": RegistryEntry(
                area_id="area52",
                device_id="device123",
                entity_id="test_domain.renamed",
                has_entity_name=True,
                name="User name",
                original_name="Hello World",
                platform="test_platform",
                unique_id="3456",
            ),
            "test_domain.boring": RegistryEntry(
                entity_id="test_domain.boring",
                platform="test_platform",
                unique_id="4567",
            ),
            "test_domain.disabled": RegistryEntry(
                disabled_by=RegistryEntryDisabler.USER,
                entity_id="test_domain.disabled",
                hidden_by=RegistryEntryHider.USER,
                platform="test_platform",
                unique_id="789A",
            ),
            "test_domain.hidden": RegistryEntry(
                entity_id="test_domain.hidden",
                hidden_by=RegistryEntryHider.USER,
                platform="test_platform",
                unique_id="89AB",
            ),
            "sensor.default_precision": RegistryEntry(
                entity_id="sensor.default_precision",
                options={"sensor": {"suggested_display_precision": 0}},
                platform="test_platform",
                unique_id="9ABC",
            ),
            "sensor.user_precision": RegistryEntry(
                entity_id="sensor.user_precision",
                options={
                    "sensor": {"display_precision": 0, "suggested_display_precision": 1}
                },
                platform="test_platform",
                unique_id="ABCD",
            ),
        },
    )

    await client.send_json_auto_id({"type": "config/entity_registry/list_for_display"})
    msg = await client.receive_json()

    assert msg["result"] == {
        "entity_categories": {"0": "config", "1": "diagnostic"},
        "entities": [
            {
                "ai": "area52",
                "di": "device123",
                "ec": 1,
                "ei": "test_domain.test",
                "en": "Hello World",
                "hn": True,
                "ic": "mdi:icon",
                "lb": [],
                "pl": "test_platform",
                "tk": "translations_galore",
            },
            {
                "ai": "area52",
                "di": "device123",
                "ei": "test_domain.nameless",
                "hn": True,
                "lb": [],
                "pl": "test_platform",
            },
            {
                "ai": "area52",
                "di": "device123",
                "ei": "test_domain.renamed",
                "en": "User name",
                "hn": True,
                "lb": [],
                "pl": "test_platform",
            },
            {
                "ei": "test_domain.boring",
                "lb": [],
                "pl": "test_platform",
            },
            {
                "ei": "test_domain.hidden",
                "lb": [],
                "hb": True,
                "pl": "test_platform",
            },
            {
                "dp": 0,
                "ei": "sensor.default_precision",
                "lb": [],
                "pl": "test_platform",
            },
            {
                "dp": 0,
                "ei": "sensor.user_precision",
                "lb": [],
                "pl": "test_platform",
            },
        ],
    }

    class Unserializable:
        """Good luck serializing me."""

    mock_registry(
        hass,
        {
            "test_domain.test": RegistryEntry(
                area_id="area52",
                device_id="device123",
                entity_id="test_domain.test",
                has_entity_name=True,
                original_name="Hello World",
                platform="test_platform",
                unique_id="1234",
            ),
            "test_domain.name_2": RegistryEntry(
                entity_id="test_domain.name_2",
                has_entity_name=True,
                original_name=Unserializable(),
                platform="test_platform",
                unique_id="6789",
            ),
        },
    )

    await client.send_json_auto_id({"type": "config/entity_registry/list_for_display"})
    msg = await client.receive_json()

    assert msg["result"] == {
        "entity_categories": {"0": "config", "1": "diagnostic"},
        "entities": [
            {
                "ai": "area52",
                "di": "device123",
                "ei": "test_domain.test",
                "hn": True,
                "lb": [],
                "en": "Hello World",
                "pl": "test_platform",
            },
        ],
    }


async def test_get_entity(hass: HomeAssistant, client: MockHAClientWebSocket) -> None:
    """Test get entry."""
    name_created_at = datetime(1994, 2, 14, 12, 0, 0)
    no_name_created_at = datetime(2024, 2, 14, 12, 0, 1)
    mock_registry(
        hass,
        {
            "test_domain.name": RegistryEntry(
                entity_id="test_domain.name",
                unique_id="1234",
                platform="test_platform",
                name="Hello World",
                created_at=name_created_at,
                modified_at=name_created_at,
            ),
            "test_domain.no_name": RegistryEntry(
                entity_id="test_domain.no_name",
                unique_id="6789",
                platform="test_platform",
                created_at=no_name_created_at,
                modified_at=no_name_created_at,
            ),
        },
    )

    await client.send_json_auto_id(
        {"type": "config/entity_registry/get", "entity_id": "test_domain.name"}
    )
    msg = await client.receive_json()

    assert msg["result"] == {
        "aliases": [],
        "area_id": None,
        "capabilities": None,
        "categories": {},
        "config_entry_id": None,
        "config_subentry_id": None,
        "created_at": name_created_at.timestamp(),
        "device_class": None,
        "device_id": None,
        "disabled_by": None,
        "entity_category": None,
        "entity_id": "test_domain.name",
        "has_entity_name": False,
        "hidden_by": None,
        "icon": None,
        "id": ANY,
        "labels": [],
        "modified_at": name_created_at.timestamp(),
        "name": "Hello World",
        "options": {},
        "original_device_class": None,
        "original_icon": None,
        "original_name": None,
        "platform": "test_platform",
        "translation_key": None,
        "unique_id": "1234",
    }

    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/get",
            "entity_id": "test_domain.no_name",
        }
    )
    msg = await client.receive_json()

    assert msg["result"] == {
        "aliases": [],
        "area_id": None,
        "capabilities": None,
        "categories": {},
        "config_entry_id": None,
        "config_subentry_id": None,
        "created_at": no_name_created_at.timestamp(),
        "device_class": None,
        "device_id": None,
        "disabled_by": None,
        "entity_category": None,
        "entity_id": "test_domain.no_name",
        "has_entity_name": False,
        "hidden_by": None,
        "icon": None,
        "id": ANY,
        "labels": [],
        "modified_at": no_name_created_at.timestamp(),
        "name": None,
        "options": {},
        "original_device_class": None,
        "original_icon": None,
        "original_name": None,
        "platform": "test_platform",
        "translation_key": None,
        "unique_id": "6789",
    }


async def test_get_entities(hass: HomeAssistant, client: MockHAClientWebSocket) -> None:
    """Test get entry."""
    name_created_at = datetime(1994, 2, 14, 12, 0, 0)
    no_name_created_at = datetime(2024, 2, 14, 12, 0, 1)
    mock_registry(
        hass,
        {
            "test_domain.name": RegistryEntry(
                entity_id="test_domain.name",
                unique_id="1234",
                platform="test_platform",
                name="Hello World",
                created_at=name_created_at,
                modified_at=name_created_at,
            ),
            "test_domain.no_name": RegistryEntry(
                entity_id="test_domain.no_name",
                unique_id="6789",
                platform="test_platform",
                created_at=no_name_created_at,
                modified_at=no_name_created_at,
            ),
        },
    )

    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/get_entries",
            "entity_ids": [
                "test_domain.name",
                "test_domain.no_name",
                "test_domain.no_such_entity",
            ],
        }
    )
    msg = await client.receive_json()

    assert msg["result"] == {
        "test_domain.name": {
            "aliases": [],
            "area_id": None,
            "capabilities": None,
            "categories": {},
            "config_entry_id": None,
            "config_subentry_id": None,
            "created_at": name_created_at.timestamp(),
            "device_class": None,
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.name",
            "has_entity_name": False,
            "hidden_by": None,
            "icon": None,
            "id": ANY,
            "labels": [],
            "modified_at": name_created_at.timestamp(),
            "name": "Hello World",
            "options": {},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "translation_key": None,
            "unique_id": "1234",
        },
        "test_domain.no_name": {
            "aliases": [],
            "area_id": None,
            "capabilities": None,
            "categories": {},
            "config_entry_id": None,
            "config_subentry_id": None,
            "created_at": no_name_created_at.timestamp(),
            "device_class": None,
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.no_name",
            "has_entity_name": False,
            "hidden_by": None,
            "icon": None,
            "id": ANY,
            "labels": [],
            "modified_at": no_name_created_at.timestamp(),
            "name": None,
            "options": {},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "translation_key": None,
            "unique_id": "6789",
        },
        "test_domain.no_such_entity": None,
    }


async def test_update_entity(
    hass: HomeAssistant, client: MockHAClientWebSocket, freezer: FrozenDateTimeFactory
) -> None:
    """Test updating entity."""
    created = datetime.fromisoformat("2024-02-14T12:00:00.900075+00:00")
    freezer.move_to(created)
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

    modified = datetime.fromisoformat("2024-07-17T13:30:00.900075+00:00")
    freezer.move_to(modified)

    # Update area, categories, device_class, hidden_by, icon, labels & name
    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "aliases": ["alias_1", "alias_2"],
            "area_id": "mock-area-id",
            "categories": {"scope1": "id", "scope2": "id"},
            "device_class": "custom_device_class",
            "hidden_by": "user",  # We exchange strings over the WS API, not enums
            "icon": "icon:after update",
            "labels": ["label1", "label2"],
            "name": "after update",
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "entity_entry": {
            "aliases": unordered(["alias_1", "alias_2"]),
            "area_id": "mock-area-id",
            "capabilities": None,
            "categories": {"scope1": "id", "scope2": "id"},
            "created_at": created.timestamp(),
            "config_entry_id": None,
            "config_subentry_id": None,
            "device_class": "custom_device_class",
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.world",
            "has_entity_name": False,
            "hidden_by": "user",  # We exchange strings over the WS API, not enums
            "icon": "icon:after update",
            "id": ANY,
            "labels": unordered(["label1", "label2"]),
            "modified_at": modified.timestamp(),
            "name": "after update",
            "options": {},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "translation_key": None,
            "unique_id": "1234",
        }
    }

    state = hass.states.get("test_domain.world")
    assert state.name == "after update"
    assert state.attributes[ATTR_ICON] == "icon:after update"

    modified = datetime.fromisoformat("2024-07-20T00:00:00.900075+00:00")
    freezer.move_to(modified)

    # Update hidden_by to illegal value
    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "hidden_by": "ivy",
        }
    )

    msg = await client.receive_json()
    assert not msg["success"]

    assert registry.entities["test_domain.world"].hidden_by is RegistryEntryHider.USER

    # Update disabled_by to user
    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "disabled_by": "user",  # We exchange strings over the WS API, not enums
        }
    )

    msg = await client.receive_json()
    assert msg["success"]

    assert hass.states.get("test_domain.world") is None
    entry = registry.entities["test_domain.world"]
    assert entry.disabled_by is RegistryEntryDisabler.USER
    assert entry.created_at == created
    assert entry.modified_at == modified

    modified = datetime.fromisoformat("2024-07-21T00:00:00.900075+00:00")
    freezer.move_to(modified)

    # Update disabled_by to None
    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "disabled_by": None,
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "entity_entry": {
            "aliases": unordered(["alias_1", "alias_2"]),
            "area_id": "mock-area-id",
            "capabilities": None,
            "categories": {"scope1": "id", "scope2": "id"},
            "config_entry_id": None,
            "config_subentry_id": None,
            "created_at": created.timestamp(),
            "device_class": "custom_device_class",
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.world",
            "has_entity_name": False,
            "hidden_by": "user",  # We exchange strings over the WS API, not enums
            "icon": "icon:after update",
            "id": ANY,
            "labels": unordered(["label1", "label2"]),
            "modified_at": modified.timestamp(),
            "name": "after update",
            "options": {},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "translation_key": None,
            "unique_id": "1234",
        },
        "require_restart": True,
    }

    modified = datetime.fromisoformat("2024-07-22T00:00:00.900075+00:00")
    freezer.move_to(modified)

    # Update entity option
    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "options_domain": "sensor",
            "options": {"unit_of_measurement": "beard_second"},
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "entity_entry": {
            "aliases": unordered(["alias_1", "alias_2"]),
            "area_id": "mock-area-id",
            "capabilities": None,
            "categories": {"scope1": "id", "scope2": "id"},
            "config_entry_id": None,
            "config_subentry_id": None,
            "created_at": created.timestamp(),
            "device_class": "custom_device_class",
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.world",
            "has_entity_name": False,
            "hidden_by": "user",  # We exchange strings over the WS API, not enums
            "icon": "icon:after update",
            "id": ANY,
            "labels": unordered(["label1", "label2"]),
            "modified_at": modified.timestamp(),
            "name": "after update",
            "options": {"sensor": {"unit_of_measurement": "beard_second"}},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "translation_key": None,
            "unique_id": "1234",
        },
    }

    modified = datetime.fromisoformat("2024-07-23T00:00:00.900075+00:00")
    freezer.move_to(modified)

    # Add a category to the entity
    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "categories": {"scope3": "id"},
        }
    )

    msg = await client.receive_json()
    assert msg["success"]

    assert msg["result"] == {
        "entity_entry": {
            "aliases": unordered(["alias_1", "alias_2"]),
            "area_id": "mock-area-id",
            "capabilities": None,
            "categories": {"scope1": "id", "scope2": "id", "scope3": "id"},
            "config_entry_id": None,
            "config_subentry_id": None,
            "created_at": created.timestamp(),
            "device_class": "custom_device_class",
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.world",
            "has_entity_name": False,
            "hidden_by": "user",  # We exchange strings over the WS API, not enums
            "icon": "icon:after update",
            "id": ANY,
            "labels": unordered(["label1", "label2"]),
            "modified_at": modified.timestamp(),
            "name": "after update",
            "options": {"sensor": {"unit_of_measurement": "beard_second"}},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "translation_key": None,
            "unique_id": "1234",
        },
    }

    modified = datetime.fromisoformat("2024-07-24T00:00:00.900075+00:00")
    freezer.move_to(modified)

    # Move the entity to a different category
    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "categories": {"scope3": "other_id"},
        }
    )

    msg = await client.receive_json()
    assert msg["success"]

    assert msg["result"] == {
        "entity_entry": {
            "aliases": unordered(["alias_1", "alias_2"]),
            "area_id": "mock-area-id",
            "capabilities": None,
            "categories": {"scope1": "id", "scope2": "id", "scope3": "other_id"},
            "config_entry_id": None,
            "config_subentry_id": None,
            "created_at": created.timestamp(),
            "device_class": "custom_device_class",
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.world",
            "has_entity_name": False,
            "hidden_by": "user",  # We exchange strings over the WS API, not enums
            "icon": "icon:after update",
            "id": ANY,
            "labels": unordered(["label1", "label2"]),
            "modified_at": modified.timestamp(),
            "name": "after update",
            "options": {"sensor": {"unit_of_measurement": "beard_second"}},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "translation_key": None,
            "unique_id": "1234",
        },
    }

    modified = datetime.fromisoformat("2024-07-23T10:00:00.900075+00:00")
    freezer.move_to(modified)

    # Move the entity to a different category
    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "categories": {"scope2": None},
        }
    )

    msg = await client.receive_json()
    assert msg["success"]

    assert msg["result"] == {
        "entity_entry": {
            "aliases": unordered(["alias_1", "alias_2"]),
            "area_id": "mock-area-id",
            "capabilities": None,
            "categories": {"scope1": "id", "scope3": "other_id"},
            "config_entry_id": None,
            "config_subentry_id": None,
            "created_at": created.timestamp(),
            "device_class": "custom_device_class",
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.world",
            "has_entity_name": False,
            "hidden_by": "user",  # We exchange strings over the WS API, not enums
            "icon": "icon:after update",
            "id": ANY,
            "labels": unordered(["label1", "label2"]),
            "modified_at": modified.timestamp(),
            "name": "after update",
            "options": {"sensor": {"unit_of_measurement": "beard_second"}},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "translation_key": None,
            "unique_id": "1234",
        },
    }


async def test_update_entity_require_restart(
    hass: HomeAssistant, client: MockHAClientWebSocket, freezer: FrozenDateTimeFactory
) -> None:
    """Test updating entity."""
    created = datetime.fromisoformat("2024-02-14T12:00:00+00:00")
    freezer.move_to(created)
    entity_id = "test_domain.test_platform_1234"
    config_entry = MockConfigEntry(domain="test_platform")
    config_entry.add_to_hass(hass)
    platform = MockEntityPlatform(hass)
    platform.config_entry = config_entry
    entity = MockEntity(unique_id="1234")
    await platform.async_add_entities([entity])

    state = hass.states.get(entity_id)
    assert state is not None

    modified = datetime.fromisoformat("2024-07-20T13:30:00+00:00")
    freezer.move_to(modified)

    # UPDATE DISABLED_BY TO NONE
    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/update",
            "entity_id": entity_id,
            "disabled_by": None,
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "entity_entry": {
            "aliases": [],
            "area_id": None,
            "capabilities": None,
            "categories": {},
            "config_entry_id": config_entry.entry_id,
            "config_subentry_id": None,
            "created_at": created.timestamp(),
            "device_class": None,
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": entity_id,
            "has_entity_name": False,
            "hidden_by": None,
            "icon": None,
            "id": ANY,
            "labels": [],
            "modified_at": created.timestamp(),
            "name": None,
            "options": {},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "translation_key": None,
            "unique_id": "1234",
        },
        "require_restart": True,
    }


async def test_enable_entity_disabled_device(
    hass: HomeAssistant,
    client: MockHAClientWebSocket,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test enabling entity of disabled device."""
    entity_id = "test_domain.test_platform_1234"
    config_entry = MockConfigEntry(domain="test_platform")
    config_entry.add_to_hass(hass)

    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
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

    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry.config_entry_id == config_entry.entry_id
    assert entity_entry.device_id == device.id
    assert entity_entry.disabled_by == RegistryEntryDisabler.DEVICE

    # UPDATE DISABLED_BY TO NONE
    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/update",
            "entity_id": entity_id,
            "disabled_by": None,
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]


async def test_update_entity_no_changes(
    hass: HomeAssistant, client: MockHAClientWebSocket, freezer: FrozenDateTimeFactory
) -> None:
    """Test update entity with no changes."""
    created = datetime.fromisoformat("2024-02-14T12:00:00.900075+00:00")
    freezer.move_to(created)
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

    modified = datetime.fromisoformat("2024-07-20T13:30:00.900075+00:00")
    freezer.move_to(modified)

    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "name": "name of entity",
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "entity_entry": {
            "aliases": [],
            "area_id": None,
            "capabilities": None,
            "categories": {},
            "config_entry_id": None,
            "config_subentry_id": None,
            "created_at": created.timestamp(),
            "device_class": None,
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.world",
            "has_entity_name": False,
            "hidden_by": None,
            "icon": None,
            "id": ANY,
            "labels": [],
            "modified_at": created.timestamp(),
            "name": "name of entity",
            "options": {},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "translation_key": None,
            "unique_id": "1234",
        }
    }

    state = hass.states.get("test_domain.world")
    assert state.name == "name of entity"


async def test_get_nonexisting_entity(client: MockHAClientWebSocket) -> None:
    """Test get entry with nonexisting entity."""
    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/get",
            "entity_id": "test_domain.no_name",
        }
    )
    msg = await client.receive_json()

    assert not msg["success"]


async def test_update_nonexisting_entity(client: MockHAClientWebSocket) -> None:
    """Test update a nonexisting entity."""
    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.no_name",
            "name": "new-name",
        }
    )
    msg = await client.receive_json()

    assert not msg["success"]


async def test_update_entity_id(
    hass: HomeAssistant, client: MockHAClientWebSocket, freezer: FrozenDateTimeFactory
) -> None:
    """Test update entity id."""
    created = datetime.fromisoformat("2024-02-14T12:00:00.900075+00:00")
    freezer.move_to(created)
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

    modified = datetime.fromisoformat("2024-07-20T13:30:00.900075+00:00")
    freezer.move_to(modified)

    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "new_entity_id": "test_domain.planet",
        }
    )

    msg = await client.receive_json()

    assert msg["result"] == {
        "entity_entry": {
            "aliases": [],
            "area_id": None,
            "capabilities": None,
            "categories": {},
            "config_entry_id": None,
            "config_subentry_id": None,
            "created_at": created.timestamp(),
            "device_class": None,
            "device_id": None,
            "disabled_by": None,
            "entity_category": None,
            "entity_id": "test_domain.planet",
            "has_entity_name": False,
            "hidden_by": None,
            "icon": None,
            "id": ANY,
            "labels": [],
            "modified_at": modified.timestamp(),
            "name": None,
            "options": {},
            "original_device_class": None,
            "original_icon": None,
            "original_name": None,
            "platform": "test_platform",
            "translation_key": None,
            "unique_id": "1234",
        }
    }

    assert hass.states.get("test_domain.world") is None
    assert hass.states.get("test_domain.planet") is not None


async def test_update_existing_entity_id(
    hass: HomeAssistant, client: MockHAClientWebSocket
) -> None:
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

    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "new_entity_id": "test_domain.planet",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]


async def test_update_invalid_entity_id(
    hass: HomeAssistant, client: MockHAClientWebSocket
) -> None:
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

    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/update",
            "entity_id": "test_domain.world",
            "new_entity_id": "another_domain.planet",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]


async def test_remove_entity(
    hass: HomeAssistant, client: MockHAClientWebSocket
) -> None:
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

    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/remove",
            "entity_id": "test_domain.world",
        }
    )

    msg = await client.receive_json()

    assert msg["success"]
    assert len(registry.entities) == 0


async def test_remove_non_existing_entity(
    hass: HomeAssistant, client: MockHAClientWebSocket
) -> None:
    """Test removing non existing entity."""
    mock_registry(hass, {})

    await client.send_json_auto_id(
        {
            "type": "config/entity_registry/remove",
            "entity_id": "test_domain.world",
        }
    )

    msg = await client.receive_json()

    assert not msg["success"]
