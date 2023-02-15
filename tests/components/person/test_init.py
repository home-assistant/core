"""The tests for the person component."""
import logging
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import person
from homeassistant.components.device_tracker import ATTR_SOURCE_TYPE, SourceType
from homeassistant.components.person import ATTR_SOURCE, ATTR_USER_ID, DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    ATTR_GPS_ACCURACY,
    ATTR_ID,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    EVENT_HOMEASSISTANT_START,
    SERVICE_RELOAD,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, CoreState, HomeAssistant, State
from homeassistant.helpers import collection, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockUser, mock_component, mock_restore_cache
from tests.typing import WebSocketGenerator

DEVICE_TRACKER = "device_tracker.test_tracker"
DEVICE_TRACKER_2 = "device_tracker.test_tracker_2"


@pytest.fixture
def storage_collection(hass):
    """Return an empty storage collection."""
    id_manager = collection.IDManager()
    return person.PersonStorageCollection(
        person.PersonStore(hass, person.STORAGE_VERSION, person.STORAGE_KEY),
        logging.getLogger(f"{person.__name__}.storage_collection"),
        id_manager,
        collection.YamlCollection(
            logging.getLogger(f"{person.__name__}.yaml_collection"), id_manager
        ),
    )


@pytest.fixture
def storage_setup(hass, hass_storage, hass_admin_user):
    """Storage setup."""
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        "data": {
            "persons": [
                {
                    "id": "1234",
                    "name": "tracked person",
                    "user_id": hass_admin_user.id,
                    "device_trackers": [DEVICE_TRACKER],
                }
            ]
        },
    }
    assert hass.loop.run_until_complete(async_setup_component(hass, DOMAIN, {}))


async def test_minimal_setup(hass: HomeAssistant) -> None:
    """Test minimal config with only name."""
    config = {DOMAIN: {"id": "1234", "name": "test person"}}
    assert await async_setup_component(hass, DOMAIN, config)

    state = hass.states.get("person.test_person")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) is None
    assert state.attributes.get(ATTR_USER_ID) is None
    assert state.attributes.get(ATTR_ENTITY_PICTURE) is None


async def test_setup_no_id(hass: HomeAssistant) -> None:
    """Test config with no id."""
    config = {DOMAIN: {"name": "test user"}}
    assert not await async_setup_component(hass, DOMAIN, config)


async def test_setup_no_name(hass: HomeAssistant) -> None:
    """Test config with no name."""
    config = {DOMAIN: {"id": "1234"}}
    assert not await async_setup_component(hass, DOMAIN, config)


async def test_setup_user_id(hass: HomeAssistant, hass_admin_user: MockUser) -> None:
    """Test config with user id."""
    user_id = hass_admin_user.id
    config = {DOMAIN: {"id": "1234", "name": "test person", "user_id": user_id}}
    assert await async_setup_component(hass, DOMAIN, config)

    state = hass.states.get("person.test_person")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ID) == "1234"
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) is None
    assert state.attributes.get(ATTR_USER_ID) == user_id


async def test_valid_invalid_user_ids(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test a person with valid user id and a person with invalid user id ."""
    user_id = hass_admin_user.id
    config = {
        DOMAIN: [
            {"id": "1234", "name": "test valid user", "user_id": user_id},
            {"id": "5678", "name": "test bad user", "user_id": "bad_user_id"},
        ]
    }
    assert await async_setup_component(hass, DOMAIN, config)

    state = hass.states.get("person.test_valid_user")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ID) == "1234"
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) is None
    assert state.attributes.get(ATTR_USER_ID) == user_id
    state = hass.states.get("person.test_bad_user")
    assert state is None


async def test_setup_tracker(hass: HomeAssistant, hass_admin_user: MockUser) -> None:
    """Test set up person with one device tracker."""
    hass.state = CoreState.not_running
    user_id = hass_admin_user.id
    config = {
        DOMAIN: {
            "id": "1234",
            "name": "tracked person",
            "user_id": user_id,
            "device_trackers": DEVICE_TRACKER,
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)

    state = hass.states.get("person.tracked_person")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ID) == "1234"
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) is None
    assert state.attributes.get(ATTR_USER_ID) == user_id

    hass.states.async_set(DEVICE_TRACKER, "home")
    await hass.async_block_till_done()

    state = hass.states.get("person.tracked_person")
    assert state.state == STATE_UNKNOWN

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    state = hass.states.get("person.tracked_person")
    assert state.state == "home"
    assert state.attributes.get(ATTR_ID) == "1234"
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER
    assert state.attributes.get(ATTR_USER_ID) == user_id

    hass.states.async_set(
        DEVICE_TRACKER,
        "not_home",
        {ATTR_LATITUDE: 10.123456, ATTR_LONGITUDE: 11.123456, ATTR_GPS_ACCURACY: 10},
    )
    await hass.async_block_till_done()

    state = hass.states.get("person.tracked_person")
    assert state.state == "not_home"
    assert state.attributes.get(ATTR_ID) == "1234"
    assert state.attributes.get(ATTR_LATITUDE) == 10.123456
    assert state.attributes.get(ATTR_LONGITUDE) == 11.123456
    assert state.attributes.get(ATTR_GPS_ACCURACY) == 10
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER
    assert state.attributes.get(ATTR_USER_ID) == user_id


async def test_setup_two_trackers(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test set up person with two device trackers."""
    hass.state = CoreState.not_running
    user_id = hass_admin_user.id
    config = {
        DOMAIN: {
            "id": "1234",
            "name": "tracked person",
            "user_id": user_id,
            "device_trackers": [DEVICE_TRACKER, DEVICE_TRACKER_2],
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)

    state = hass.states.get("person.tracked_person")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ID) == "1234"
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) is None
    assert state.attributes.get(ATTR_USER_ID) == user_id

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    hass.states.async_set(DEVICE_TRACKER, "home", {ATTR_SOURCE_TYPE: SourceType.ROUTER})
    await hass.async_block_till_done()

    state = hass.states.get("person.tracked_person")
    assert state.state == "home"
    assert state.attributes.get(ATTR_ID) == "1234"
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_GPS_ACCURACY) is None
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER
    assert state.attributes.get(ATTR_USER_ID) == user_id

    hass.states.async_set(
        DEVICE_TRACKER_2,
        "not_home",
        {
            ATTR_LATITUDE: 12.123456,
            ATTR_LONGITUDE: 13.123456,
            ATTR_GPS_ACCURACY: 12,
            ATTR_SOURCE_TYPE: SourceType.GPS,
        },
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        DEVICE_TRACKER, "not_home", {ATTR_SOURCE_TYPE: SourceType.ROUTER}
    )
    await hass.async_block_till_done()

    state = hass.states.get("person.tracked_person")
    assert state.state == "not_home"
    assert state.attributes.get(ATTR_ID) == "1234"
    assert state.attributes.get(ATTR_LATITUDE) == 12.123456
    assert state.attributes.get(ATTR_LONGITUDE) == 13.123456
    assert state.attributes.get(ATTR_GPS_ACCURACY) == 12
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER_2
    assert state.attributes.get(ATTR_USER_ID) == user_id

    hass.states.async_set(DEVICE_TRACKER_2, "zone1", {ATTR_SOURCE_TYPE: SourceType.GPS})
    await hass.async_block_till_done()

    state = hass.states.get("person.tracked_person")
    assert state.state == "zone1"
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER_2

    hass.states.async_set(DEVICE_TRACKER, "home", {ATTR_SOURCE_TYPE: SourceType.ROUTER})
    await hass.async_block_till_done()
    hass.states.async_set(DEVICE_TRACKER_2, "zone2", {ATTR_SOURCE_TYPE: SourceType.GPS})
    await hass.async_block_till_done()

    state = hass.states.get("person.tracked_person")
    assert state.state == "home"
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER


async def test_ignore_unavailable_states(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test set up person with two device trackers, one unavailable."""
    hass.state = CoreState.not_running
    user_id = hass_admin_user.id
    config = {
        DOMAIN: {
            "id": "1234",
            "name": "tracked person",
            "user_id": user_id,
            "device_trackers": [DEVICE_TRACKER, DEVICE_TRACKER_2],
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)

    state = hass.states.get("person.tracked_person")
    assert state.state == STATE_UNKNOWN

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    hass.states.async_set(DEVICE_TRACKER, "home")
    await hass.async_block_till_done()
    hass.states.async_set(DEVICE_TRACKER, "unavailable")
    await hass.async_block_till_done()

    # Unknown, as only 1 device tracker has a state, but we ignore that one
    state = hass.states.get("person.tracked_person")
    assert state.state == STATE_UNKNOWN

    hass.states.async_set(DEVICE_TRACKER_2, "not_home")
    await hass.async_block_till_done()

    # Take state of tracker 2
    state = hass.states.get("person.tracked_person")
    assert state.state == "not_home"

    # state 1 is newer but ignored, keep tracker 2 state
    hass.states.async_set(DEVICE_TRACKER, "unknown")
    await hass.async_block_till_done()

    state = hass.states.get("person.tracked_person")
    assert state.state == "not_home"


async def test_restore_home_state(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test that the state is restored for a person on startup."""
    user_id = hass_admin_user.id
    attrs = {
        ATTR_ID: "1234",
        ATTR_LATITUDE: 10.12346,
        ATTR_LONGITUDE: 11.12346,
        ATTR_SOURCE: DEVICE_TRACKER,
        ATTR_USER_ID: user_id,
    }
    state = State("person.tracked_person", "home", attrs)
    mock_restore_cache(hass, (state,))
    hass.state = CoreState.not_running
    mock_component(hass, "recorder")
    config = {
        DOMAIN: {
            "id": "1234",
            "name": "tracked person",
            "user_id": user_id,
            "device_trackers": DEVICE_TRACKER,
            "picture": "/bla",
        }
    }
    assert await async_setup_component(hass, DOMAIN, config)

    state = hass.states.get("person.tracked_person")
    assert state.state == "home"
    assert state.attributes.get(ATTR_ID) == "1234"
    assert state.attributes.get(ATTR_LATITUDE) == 10.12346
    assert state.attributes.get(ATTR_LONGITUDE) == 11.12346
    # When restoring state the entity_id of the person will be used as source.
    assert state.attributes.get(ATTR_SOURCE) == "person.tracked_person"
    assert state.attributes.get(ATTR_USER_ID) == user_id
    assert state.attributes.get(ATTR_ENTITY_PICTURE) == "/bla"


async def test_duplicate_ids(hass: HomeAssistant, hass_admin_user: MockUser) -> None:
    """Test we don't allow duplicate IDs."""
    config = {
        DOMAIN: [
            {"id": "1234", "name": "test user 1"},
            {"id": "1234", "name": "test user 2"},
        ]
    }
    assert await async_setup_component(hass, DOMAIN, config)

    assert len(hass.states.async_entity_ids("person")) == 1
    assert hass.states.get("person.test_user_1") is not None
    assert hass.states.get("person.test_user_2") is None


async def test_create_person_during_run(hass: HomeAssistant) -> None:
    """Test that person is updated if created while hass is running."""
    config = {DOMAIN: {}}
    assert await async_setup_component(hass, DOMAIN, config)
    hass.states.async_set(DEVICE_TRACKER, "home")
    await hass.async_block_till_done()

    await hass.components.person.async_create_person(
        "tracked person", device_trackers=[DEVICE_TRACKER]
    )
    await hass.async_block_till_done()

    state = hass.states.get("person.tracked_person")
    assert state.state == "home"


async def test_load_person_storage(
    hass: HomeAssistant, hass_admin_user: MockUser, storage_setup
) -> None:
    """Test set up person from storage."""
    state = hass.states.get("person.tracked_person")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ID) == "1234"
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) is None
    assert state.attributes.get(ATTR_USER_ID) == hass_admin_user.id

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    hass.states.async_set(DEVICE_TRACKER, "home")
    await hass.async_block_till_done()

    state = hass.states.get("person.tracked_person")
    assert state.state == "home"
    assert state.attributes.get(ATTR_ID) == "1234"
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER
    assert state.attributes.get(ATTR_USER_ID) == hass_admin_user.id


async def test_load_person_storage_two_nonlinked(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test loading two users with both not having a user linked."""
    hass_storage[DOMAIN] = {
        "key": DOMAIN,
        "version": 1,
        "data": {
            "persons": [
                {
                    "id": "1234",
                    "name": "tracked person 1",
                    "user_id": None,
                    "device_trackers": [],
                },
                {
                    "id": "5678",
                    "name": "tracked person 2",
                    "user_id": None,
                    "device_trackers": [],
                },
            ]
        },
    }
    await async_setup_component(hass, DOMAIN, {})

    assert len(hass.states.async_entity_ids("person")) == 2
    assert hass.states.get("person.tracked_person_1") is not None
    assert hass.states.get("person.tracked_person_2") is not None


async def test_ws_list(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, storage_setup
) -> None:
    """Test listing via WS."""
    manager = hass.data[DOMAIN][1]

    client = await hass_ws_client(hass)

    resp = await client.send_json({"id": 6, "type": "person/list"})
    resp = await client.receive_json()
    assert resp["success"]
    assert resp["result"]["storage"] == manager.async_items()
    assert len(resp["result"]["storage"]) == 1
    assert len(resp["result"]["config"]) == 0


async def test_ws_create(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    storage_setup,
    hass_read_only_user: MockUser,
) -> None:
    """Test creating via WS."""
    manager = hass.data[DOMAIN][1]

    client = await hass_ws_client(hass)

    resp = await client.send_json(
        {
            "id": 6,
            "type": "person/create",
            "name": "Hello",
            "device_trackers": [DEVICE_TRACKER],
            "user_id": hass_read_only_user.id,
            "picture": "/bla",
        }
    )
    resp = await client.receive_json()

    persons = manager.async_items()
    assert len(persons) == 2

    assert resp["success"]
    assert resp["result"] == persons[1]


async def test_ws_create_requires_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    storage_setup,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test creating via WS requires admin."""
    hass_admin_user.groups = []
    manager = hass.data[DOMAIN][1]

    client = await hass_ws_client(hass)

    resp = await client.send_json(
        {
            "id": 6,
            "type": "person/create",
            "name": "Hello",
            "device_trackers": [DEVICE_TRACKER],
            "user_id": hass_read_only_user.id,
        }
    )
    resp = await client.receive_json()

    persons = manager.async_items()
    assert len(persons) == 1

    assert not resp["success"]


async def test_ws_update(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, storage_setup
) -> None:
    """Test updating via WS."""
    manager = hass.data[DOMAIN][1]

    client = await hass_ws_client(hass)
    persons = manager.async_items()

    resp = await client.send_json(
        {
            "id": 6,
            "type": "person/update",
            "person_id": persons[0]["id"],
            "user_id": persons[0]["user_id"],
        }
    )
    resp = await client.receive_json()

    assert resp["success"]

    resp = await client.send_json(
        {
            "id": 7,
            "type": "person/update",
            "person_id": persons[0]["id"],
            "name": "Updated Name",
            "device_trackers": [DEVICE_TRACKER_2],
            "user_id": None,
            "picture": "/bla",
        }
    )
    resp = await client.receive_json()

    persons = manager.async_items()
    assert len(persons) == 1

    assert resp["success"]
    assert resp["result"] == persons[0]
    assert persons[0]["name"] == "Updated Name"
    assert persons[0]["name"] == "Updated Name"
    assert persons[0]["device_trackers"] == [DEVICE_TRACKER_2]
    assert persons[0]["user_id"] is None
    assert persons[0]["picture"] == "/bla"

    state = hass.states.get("person.tracked_person")
    assert state.name == "Updated Name"


async def test_ws_update_require_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    storage_setup,
    hass_admin_user: MockUser,
) -> None:
    """Test updating via WS requires admin."""
    hass_admin_user.groups = []
    manager = hass.data[DOMAIN][1]

    client = await hass_ws_client(hass)
    original = dict(manager.async_items()[0])

    resp = await client.send_json(
        {
            "id": 6,
            "type": "person/update",
            "person_id": original["id"],
            "name": "Updated Name",
            "device_trackers": [DEVICE_TRACKER_2],
            "user_id": None,
        }
    )
    resp = await client.receive_json()
    assert not resp["success"]

    not_updated = dict(manager.async_items()[0])
    assert original == not_updated


async def test_ws_delete(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, storage_setup
) -> None:
    """Test deleting via WS."""
    manager = hass.data[DOMAIN][1]

    client = await hass_ws_client(hass)
    persons = manager.async_items()

    resp = await client.send_json(
        {"id": 6, "type": "person/delete", "person_id": persons[0]["id"]}
    )
    resp = await client.receive_json()

    persons = manager.async_items()
    assert len(persons) == 0

    assert resp["success"]
    assert len(hass.states.async_entity_ids("person")) == 0
    ent_reg = er.async_get(hass)
    assert not ent_reg.async_is_registered("person.tracked_person")


async def test_ws_delete_require_admin(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    storage_setup,
    hass_admin_user: MockUser,
) -> None:
    """Test deleting via WS requires admin."""
    hass_admin_user.groups = []
    manager = hass.data[DOMAIN][1]

    client = await hass_ws_client(hass)

    resp = await client.send_json(
        {
            "id": 6,
            "type": "person/delete",
            "person_id": manager.async_items()[0]["id"],
            "name": "Updated Name",
            "device_trackers": [DEVICE_TRACKER_2],
            "user_id": None,
        }
    )
    resp = await client.receive_json()
    assert not resp["success"]

    persons = manager.async_items()
    assert len(persons) == 1


async def test_create_invalid_user_id(hass: HomeAssistant, storage_collection) -> None:
    """Test we do not allow invalid user ID during creation."""
    with pytest.raises(ValueError):
        await storage_collection.async_create_item(
            {"name": "Hello", "user_id": "non-existing"}
        )


async def test_create_duplicate_user_id(
    hass: HomeAssistant, hass_admin_user: MockUser, storage_collection
) -> None:
    """Test we do not allow duplicate user ID during creation."""
    await storage_collection.async_create_item(
        {"name": "Hello", "user_id": hass_admin_user.id}
    )

    with pytest.raises(ValueError):
        await storage_collection.async_create_item(
            {"name": "Hello", "user_id": hass_admin_user.id}
        )


async def test_update_double_user_id(
    hass: HomeAssistant, hass_admin_user: MockUser, storage_collection
) -> None:
    """Test we do not allow double user ID during update."""
    await storage_collection.async_create_item(
        {"name": "Hello", "user_id": hass_admin_user.id}
    )
    person = await storage_collection.async_create_item({"name": "Hello"})

    with pytest.raises(ValueError):
        await storage_collection.async_update_item(
            person["id"], {"user_id": hass_admin_user.id}
        )


async def test_update_invalid_user_id(hass: HomeAssistant, storage_collection) -> None:
    """Test updating to invalid user ID."""
    person = await storage_collection.async_create_item({"name": "Hello"})

    with pytest.raises(ValueError):
        await storage_collection.async_update_item(
            person["id"], {"user_id": "non-existing"}
        )


async def test_update_person_when_user_removed(
    hass: HomeAssistant, storage_setup, hass_read_only_user: MockUser
) -> None:
    """Update person when user is removed."""
    storage_collection = hass.data[DOMAIN][1]

    person = await storage_collection.async_create_item(
        {"name": "Hello", "user_id": hass_read_only_user.id}
    )

    await hass.auth.async_remove_user(hass_read_only_user)
    await hass.async_block_till_done()

    assert storage_collection.data[person["id"]]["user_id"] is None


async def test_removing_device_tracker(hass: HomeAssistant, storage_setup) -> None:
    """Test we automatically remove removed device trackers."""
    storage_collection = hass.data[DOMAIN][1]
    reg = er.async_get(hass)
    entry = reg.async_get_or_create(
        "device_tracker", "mobile_app", "bla", suggested_object_id="pixel"
    )

    person = await storage_collection.async_create_item(
        {"name": "Hello", "device_trackers": [entry.entity_id]}
    )

    reg.async_remove(entry.entity_id)
    await hass.async_block_till_done()

    assert storage_collection.data[person["id"]]["device_trackers"] == []


async def test_add_user_device_tracker(
    hass: HomeAssistant, storage_setup, hass_read_only_user: MockUser
) -> None:
    """Test adding a device tracker to a person tied to a user."""
    storage_collection = hass.data[DOMAIN][1]
    pers = await storage_collection.async_create_item(
        {
            "name": "Hello",
            "user_id": hass_read_only_user.id,
            "device_trackers": ["device_tracker.on_create"],
        }
    )

    await person.async_add_user_device_tracker(
        hass, hass_read_only_user.id, "device_tracker.added"
    )

    assert storage_collection.data[pers["id"]]["device_trackers"] == [
        "device_tracker.on_create",
        "device_tracker.added",
    ]


async def test_reload(hass: HomeAssistant, hass_admin_user: MockUser) -> None:
    """Test reloading the YAML config."""
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: [
                {"name": "Person 1", "id": "id-1"},
                {"name": "Person 2", "id": "id-2"},
            ]
        },
    )

    assert len(hass.states.async_entity_ids()) == 2

    state_1 = hass.states.get("person.person_1")
    state_2 = hass.states.get("person.person_2")
    state_3 = hass.states.get("person.person_3")

    assert state_1 is not None
    assert state_1.name == "Person 1"
    assert state_2 is not None
    assert state_2.name == "Person 2"
    assert state_3 is None

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            DOMAIN: [
                {"name": "Person 1-updated", "id": "id-1"},
                {"name": "Person 3", "id": "id-3"},
            ]
        },
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids()) == 2

    state_1 = hass.states.get("person.person_1")
    state_2 = hass.states.get("person.person_2")
    state_3 = hass.states.get("person.person_3")

    assert state_1 is not None
    assert state_1.name == "Person 1-updated"
    assert state_2 is None
    assert state_3 is not None
    assert state_3.name == "Person 3"


async def test_person_storage_fixing_device_trackers(storage_collection) -> None:
    """Test None device trackers become lists."""
    with patch.object(
        storage_collection.store,
        "async_load",
        return_value={"items": [{"id": "bla", "name": "bla", "device_trackers": None}]},
    ):
        await storage_collection.async_load()

    assert storage_collection.data["bla"]["device_trackers"] == []


async def test_persons_with_entity(hass: HomeAssistant) -> None:
    """Test finding persons with an entity."""
    assert await async_setup_component(
        hass,
        "person",
        {
            "person": [
                {
                    "id": "abcd",
                    "name": "Paulus",
                    "device_trackers": [
                        "device_tracker.paulus_iphone",
                        "device_tracker.paulus_ipad",
                    ],
                },
                {
                    "id": "efgh",
                    "name": "Anne Therese",
                    "device_trackers": [
                        "device_tracker.at_pixel",
                    ],
                },
            ]
        },
    )

    assert person.persons_with_entity(hass, "device_tracker.paulus_iphone") == [
        "person.paulus"
    ]


async def test_entities_in_person(hass: HomeAssistant) -> None:
    """Test finding entities tracked by person."""
    assert await async_setup_component(
        hass,
        "person",
        {
            "person": [
                {
                    "id": "abcd",
                    "name": "Paulus",
                    "device_trackers": [
                        "device_tracker.paulus_iphone",
                        "device_tracker.paulus_ipad",
                    ],
                }
            ]
        },
    )

    assert person.entities_in_person(hass, "person.paulus") == [
        "device_tracker.paulus_iphone",
        "device_tracker.paulus_ipad",
    ]
