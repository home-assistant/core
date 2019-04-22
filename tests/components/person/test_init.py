"""The tests for the person component."""
from unittest.mock import Mock

import pytest

from homeassistant.components.device_tracker import (
    ATTR_SOURCE_TYPE, SOURCE_TYPE_GPS, SOURCE_TYPE_ROUTER)
from homeassistant.components.person import (
    ATTR_SOURCE, ATTR_USER_ID, DOMAIN, PersonManager)
from homeassistant.const import (
    ATTR_GPS_ACCURACY, ATTR_ID, ATTR_LATITUDE, ATTR_LONGITUDE,
    EVENT_HOMEASSISTANT_START, STATE_UNKNOWN)
from homeassistant.core import CoreState, State
from homeassistant.setup import async_setup_component

from tests.common import (
    assert_setup_component, mock_component, mock_coro_func, mock_restore_cache)

DEVICE_TRACKER = 'device_tracker.test_tracker'
DEVICE_TRACKER_2 = 'device_tracker.test_tracker_2'


# pylint: disable=redefined-outer-name
@pytest.fixture
def storage_setup(hass, hass_storage, hass_admin_user):
    """Storage setup."""
    hass_storage[DOMAIN] = {
        'key': DOMAIN,
        'version': 1,
        'data': {
            'persons': [
                {
                    'id': '1234',
                    'name': 'tracked person',
                    'user_id': hass_admin_user.id,
                    'device_trackers': [DEVICE_TRACKER]
                }
            ]
        }
    }
    assert hass.loop.run_until_complete(
        async_setup_component(hass, DOMAIN, {})
    )


async def test_minimal_setup(hass):
    """Test minimal config with only name."""
    config = {DOMAIN: {'id': '1234', 'name': 'test person'}}
    with assert_setup_component(1):
        assert await async_setup_component(hass, DOMAIN, config)

    state = hass.states.get('person.test_person')
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) is None
    assert state.attributes.get(ATTR_USER_ID) is None


async def test_setup_no_id(hass):
    """Test config with no id."""
    config = {DOMAIN: {'name': 'test user'}}
    assert not await async_setup_component(hass, DOMAIN, config)


async def test_setup_no_name(hass):
    """Test config with no name."""
    config = {DOMAIN: {'id': '1234'}}
    assert not await async_setup_component(hass, DOMAIN, config)


async def test_setup_user_id(hass, hass_admin_user):
    """Test config with user id."""
    user_id = hass_admin_user.id
    config = {
        DOMAIN: {'id': '1234', 'name': 'test person', 'user_id': user_id}}
    with assert_setup_component(1):
        assert await async_setup_component(hass, DOMAIN, config)

    state = hass.states.get('person.test_person')
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) is None
    assert state.attributes.get(ATTR_USER_ID) == user_id


async def test_valid_invalid_user_ids(hass, hass_admin_user):
    """Test a person with valid user id and a person with invalid user id ."""
    user_id = hass_admin_user.id
    config = {DOMAIN: [
        {'id': '1234', 'name': 'test valid user', 'user_id': user_id},
        {'id': '5678', 'name': 'test bad user', 'user_id': 'bad_user_id'}]}
    with assert_setup_component(2):
        assert await async_setup_component(hass, DOMAIN, config)

    state = hass.states.get('person.test_valid_user')
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) is None
    assert state.attributes.get(ATTR_USER_ID) == user_id
    state = hass.states.get('person.test_bad_user')
    assert state is None


async def test_setup_tracker(hass, hass_admin_user):
    """Test set up person with one device tracker."""
    hass.state = CoreState.not_running
    user_id = hass_admin_user.id
    config = {DOMAIN: {
        'id': '1234', 'name': 'tracked person', 'user_id': user_id,
        'device_trackers': DEVICE_TRACKER}}
    with assert_setup_component(1):
        assert await async_setup_component(hass, DOMAIN, config)

    state = hass.states.get('person.tracked_person')
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) is None
    assert state.attributes.get(ATTR_USER_ID) == user_id

    hass.states.async_set(DEVICE_TRACKER, 'home')
    await hass.async_block_till_done()

    state = hass.states.get('person.tracked_person')
    assert state.state == STATE_UNKNOWN

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()

    state = hass.states.get('person.tracked_person')
    assert state.state == 'home'
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER
    assert state.attributes.get(ATTR_USER_ID) == user_id

    hass.states.async_set(
        DEVICE_TRACKER, 'not_home', {
            ATTR_LATITUDE: 10.123456,
            ATTR_LONGITUDE: 11.123456,
            ATTR_GPS_ACCURACY: 10})
    await hass.async_block_till_done()

    state = hass.states.get('person.tracked_person')
    assert state.state == 'not_home'
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) == 10.123456
    assert state.attributes.get(ATTR_LONGITUDE) == 11.123456
    assert state.attributes.get(ATTR_GPS_ACCURACY) == 10
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER
    assert state.attributes.get(ATTR_USER_ID) == user_id


async def test_setup_two_trackers(hass, hass_admin_user):
    """Test set up person with two device trackers."""
    hass.state = CoreState.not_running
    user_id = hass_admin_user.id
    config = {DOMAIN: {
        'id': '1234', 'name': 'tracked person', 'user_id': user_id,
        'device_trackers': [DEVICE_TRACKER, DEVICE_TRACKER_2]}}
    with assert_setup_component(1):
        assert await async_setup_component(hass, DOMAIN, config)

    state = hass.states.get('person.tracked_person')
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) is None
    assert state.attributes.get(ATTR_USER_ID) == user_id

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    hass.states.async_set(
        DEVICE_TRACKER, 'home', {ATTR_SOURCE_TYPE: SOURCE_TYPE_ROUTER})
    await hass.async_block_till_done()

    state = hass.states.get('person.tracked_person')
    assert state.state == 'home'
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_GPS_ACCURACY) is None
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER
    assert state.attributes.get(ATTR_USER_ID) == user_id

    hass.states.async_set(
        DEVICE_TRACKER_2, 'not_home', {
            ATTR_LATITUDE: 12.123456,
            ATTR_LONGITUDE: 13.123456,
            ATTR_GPS_ACCURACY: 12,
            ATTR_SOURCE_TYPE: SOURCE_TYPE_GPS})
    await hass.async_block_till_done()
    hass.states.async_set(
        DEVICE_TRACKER, 'not_home', {ATTR_SOURCE_TYPE: SOURCE_TYPE_ROUTER})
    await hass.async_block_till_done()

    state = hass.states.get('person.tracked_person')
    assert state.state == 'not_home'
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) == 12.123456
    assert state.attributes.get(ATTR_LONGITUDE) == 13.123456
    assert state.attributes.get(ATTR_GPS_ACCURACY) == 12
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER_2
    assert state.attributes.get(ATTR_USER_ID) == user_id

    hass.states.async_set(
        DEVICE_TRACKER_2, 'zone1', {ATTR_SOURCE_TYPE: SOURCE_TYPE_GPS})
    await hass.async_block_till_done()

    state = hass.states.get('person.tracked_person')
    assert state.state == 'zone1'
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER_2

    hass.states.async_set(
        DEVICE_TRACKER, 'home', {ATTR_SOURCE_TYPE: SOURCE_TYPE_ROUTER})
    await hass.async_block_till_done()
    hass.states.async_set(
        DEVICE_TRACKER_2, 'zone2', {ATTR_SOURCE_TYPE: SOURCE_TYPE_GPS})
    await hass.async_block_till_done()

    state = hass.states.get('person.tracked_person')
    assert state.state == 'home'
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER


async def test_ignore_unavailable_states(hass, hass_admin_user):
    """Test set up person with two device trackers, one unavailable."""
    hass.state = CoreState.not_running
    user_id = hass_admin_user.id
    config = {DOMAIN: {
        'id': '1234', 'name': 'tracked person', 'user_id': user_id,
        'device_trackers': [DEVICE_TRACKER, DEVICE_TRACKER_2]}}
    with assert_setup_component(1):
        assert await async_setup_component(hass, DOMAIN, config)

    state = hass.states.get('person.tracked_person')
    assert state.state == STATE_UNKNOWN

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    hass.states.async_set(DEVICE_TRACKER, 'home')
    await hass.async_block_till_done()
    hass.states.async_set(DEVICE_TRACKER, 'unavailable')
    await hass.async_block_till_done()

    # Unknown, as only 1 device tracker has a state, but we ignore that one
    state = hass.states.get('person.tracked_person')
    assert state.state == STATE_UNKNOWN

    hass.states.async_set(DEVICE_TRACKER_2, 'not_home')
    await hass.async_block_till_done()

    # Take state of tracker 2
    state = hass.states.get('person.tracked_person')
    assert state.state == 'not_home'

    # state 1 is newer but ignored, keep tracker 2 state
    hass.states.async_set(DEVICE_TRACKER, 'unknown')
    await hass.async_block_till_done()

    state = hass.states.get('person.tracked_person')
    assert state.state == 'not_home'


async def test_restore_home_state(hass, hass_admin_user):
    """Test that the state is restored for a person on startup."""
    user_id = hass_admin_user.id
    attrs = {
        ATTR_ID: '1234', ATTR_LATITUDE: 10.12346, ATTR_LONGITUDE: 11.12346,
        ATTR_SOURCE: DEVICE_TRACKER, ATTR_USER_ID: user_id}
    state = State('person.tracked_person', 'home', attrs)
    mock_restore_cache(hass, (state, ))
    hass.state = CoreState.not_running
    mock_component(hass, 'recorder')
    config = {DOMAIN: {
        'id': '1234', 'name': 'tracked person', 'user_id': user_id,
        'device_trackers': DEVICE_TRACKER}}
    with assert_setup_component(1):
        assert await async_setup_component(hass, DOMAIN, config)

    state = hass.states.get('person.tracked_person')
    assert state.state == 'home'
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) == 10.12346
    assert state.attributes.get(ATTR_LONGITUDE) == 11.12346
    # When restoring state the entity_id of the person will be used as source.
    assert state.attributes.get(ATTR_SOURCE) == 'person.tracked_person'
    assert state.attributes.get(ATTR_USER_ID) == user_id


async def test_duplicate_ids(hass, hass_admin_user):
    """Test we don't allow duplicate IDs."""
    config = {DOMAIN: [
        {'id': '1234', 'name': 'test user 1'},
        {'id': '1234', 'name': 'test user 2'}]}
    with assert_setup_component(2):
        assert await async_setup_component(hass, DOMAIN, config)

    assert len(hass.states.async_entity_ids('person')) == 1
    assert hass.states.get('person.test_user_1') is not None
    assert hass.states.get('person.test_user_2') is None


async def test_create_person_during_run(hass):
    """Test that person is updated if created while hass is running."""
    config = {DOMAIN: {}}
    with assert_setup_component(0):
        assert await async_setup_component(hass, DOMAIN, config)
    hass.states.async_set(DEVICE_TRACKER, 'home')
    await hass.async_block_till_done()

    await hass.components.person.async_create_person(
        'tracked person', device_trackers=[DEVICE_TRACKER])
    await hass.async_block_till_done()

    state = hass.states.get('person.tracked_person')
    assert state.state == 'home'


async def test_load_person_storage(hass, hass_admin_user, storage_setup):
    """Test set up person from storage."""
    state = hass.states.get('person.tracked_person')
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) is None
    assert state.attributes.get(ATTR_USER_ID) == hass_admin_user.id

    hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
    await hass.async_block_till_done()
    hass.states.async_set(DEVICE_TRACKER, 'home')
    await hass.async_block_till_done()

    state = hass.states.get('person.tracked_person')
    assert state.state == 'home'
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER
    assert state.attributes.get(ATTR_USER_ID) == hass_admin_user.id


async def test_load_person_storage_two_nonlinked(hass, hass_storage):
    """Test loading two users with both not having a user linked."""
    hass_storage[DOMAIN] = {
        'key': DOMAIN,
        'version': 1,
        'data': {
            'persons': [
                {
                    'id': '1234',
                    'name': 'tracked person 1',
                    'user_id': None,
                    'device_trackers': []
                },
                {
                    'id': '5678',
                    'name': 'tracked person 2',
                    'user_id': None,
                    'device_trackers': []
                },
            ]
        }
    }
    await async_setup_component(hass, DOMAIN, {})

    assert len(hass.states.async_entity_ids('person')) == 2
    assert hass.states.get('person.tracked_person_1') is not None
    assert hass.states.get('person.tracked_person_2') is not None


async def test_ws_list(hass, hass_ws_client, storage_setup):
    """Test listing via WS."""
    manager = hass.data[DOMAIN]

    client = await hass_ws_client(hass)

    resp = await client.send_json({
        'id': 6,
        'type': 'person/list',
    })
    resp = await client.receive_json()
    assert resp['success']
    assert resp['result']['storage'] == manager.storage_persons
    assert len(resp['result']['storage']) == 1
    assert len(resp['result']['config']) == 0


async def test_ws_create(hass, hass_ws_client, storage_setup,
                         hass_read_only_user):
    """Test creating via WS."""
    manager = hass.data[DOMAIN]

    client = await hass_ws_client(hass)

    resp = await client.send_json({
        'id': 6,
        'type': 'person/create',
        'name': 'Hello',
        'device_trackers': [DEVICE_TRACKER],
        'user_id': hass_read_only_user.id,
    })
    resp = await client.receive_json()

    persons = manager.storage_persons
    assert len(persons) == 2

    assert resp['success']
    assert resp['result'] == persons[1]


async def test_ws_create_requires_admin(hass, hass_ws_client, storage_setup,
                                        hass_admin_user, hass_read_only_user):
    """Test creating via WS requires admin."""
    hass_admin_user.groups = []
    manager = hass.data[DOMAIN]

    client = await hass_ws_client(hass)

    resp = await client.send_json({
        'id': 6,
        'type': 'person/create',
        'name': 'Hello',
        'device_trackers': [DEVICE_TRACKER],
        'user_id': hass_read_only_user.id,
    })
    resp = await client.receive_json()

    persons = manager.storage_persons
    assert len(persons) == 1

    assert not resp['success']


async def test_ws_update(hass, hass_ws_client, storage_setup):
    """Test updating via WS."""
    manager = hass.data[DOMAIN]

    client = await hass_ws_client(hass)
    persons = manager.storage_persons

    resp = await client.send_json({
        'id': 6,
        'type': 'person/update',
        'person_id': persons[0]['id'],
        'name': 'Updated Name',
        'device_trackers': [DEVICE_TRACKER_2],
        'user_id': None,
    })
    resp = await client.receive_json()

    persons = manager.storage_persons
    assert len(persons) == 1

    assert resp['success']
    assert resp['result'] == persons[0]
    assert persons[0]['name'] == 'Updated Name'
    assert persons[0]['name'] == 'Updated Name'
    assert persons[0]['device_trackers'] == [DEVICE_TRACKER_2]
    assert persons[0]['user_id'] is None

    state = hass.states.get('person.tracked_person')
    assert state.name == 'Updated Name'


async def test_ws_update_require_admin(hass, hass_ws_client, storage_setup,
                                       hass_admin_user):
    """Test updating via WS requires admin."""
    hass_admin_user.groups = []
    manager = hass.data[DOMAIN]

    client = await hass_ws_client(hass)
    original = dict(manager.storage_persons[0])

    resp = await client.send_json({
        'id': 6,
        'type': 'person/update',
        'person_id': original['id'],
        'name': 'Updated Name',
        'device_trackers': [DEVICE_TRACKER_2],
        'user_id': None,
    })
    resp = await client.receive_json()
    assert not resp['success']

    not_updated = dict(manager.storage_persons[0])
    assert original == not_updated


async def test_ws_delete(hass, hass_ws_client, storage_setup):
    """Test deleting via WS."""
    manager = hass.data[DOMAIN]

    client = await hass_ws_client(hass)
    persons = manager.storage_persons

    resp = await client.send_json({
        'id': 6,
        'type': 'person/delete',
        'person_id': persons[0]['id'],
    })
    resp = await client.receive_json()

    persons = manager.storage_persons
    assert len(persons) == 0

    assert resp['success']
    assert len(hass.states.async_entity_ids('person')) == 0
    ent_reg = await hass.helpers.entity_registry.async_get_registry()
    assert not ent_reg.async_is_registered('person.tracked_person')


async def test_ws_delete_require_admin(hass, hass_ws_client, storage_setup,
                                       hass_admin_user):
    """Test deleting via WS requires admin."""
    hass_admin_user.groups = []
    manager = hass.data[DOMAIN]

    client = await hass_ws_client(hass)

    resp = await client.send_json({
        'id': 6,
        'type': 'person/delete',
        'person_id': manager.storage_persons[0]['id'],
        'name': 'Updated Name',
        'device_trackers': [DEVICE_TRACKER_2],
        'user_id': None,
    })
    resp = await client.receive_json()
    assert not resp['success']

    persons = manager.storage_persons
    assert len(persons) == 1


async def test_create_invalid_user_id(hass):
    """Test we do not allow invalid user ID during creation."""
    manager = PersonManager(hass, Mock(), [])
    await manager.async_initialize()
    with pytest.raises(ValueError):
        await manager.async_create_person(
            name='Hello',
            user_id='non-existing'
        )


async def test_create_duplicate_user_id(hass, hass_admin_user):
    """Test we do not allow duplicate user ID during creation."""
    manager = PersonManager(
        hass, Mock(async_add_entities=mock_coro_func()), []
    )
    await manager.async_initialize()
    await manager.async_create_person(
        name='Hello',
        user_id=hass_admin_user.id
    )

    with pytest.raises(ValueError):
        await manager.async_create_person(
            name='Hello',
            user_id=hass_admin_user.id
        )


async def test_update_double_user_id(hass, hass_admin_user):
    """Test we do not allow double user ID during update."""
    manager = PersonManager(
        hass, Mock(async_add_entities=mock_coro_func()), []
    )
    await manager.async_initialize()
    await manager.async_create_person(
        name='Hello',
        user_id=hass_admin_user.id
    )
    person = await manager.async_create_person(
        name='Hello',
    )

    with pytest.raises(ValueError):
        await manager.async_update_person(
            person_id=person['id'],
            user_id=hass_admin_user.id
        )


async def test_update_invalid_user_id(hass):
    """Test updating to invalid user ID."""
    manager = PersonManager(
        hass, Mock(async_add_entities=mock_coro_func()), []
    )
    await manager.async_initialize()
    person = await manager.async_create_person(
        name='Hello',
    )

    with pytest.raises(ValueError):
        await manager.async_update_person(
            person_id=person['id'],
            user_id='non-existing'
        )


async def test_update_person_when_user_removed(hass, hass_read_only_user):
    """Update person when user is removed."""
    manager = PersonManager(
        hass, Mock(async_add_entities=mock_coro_func()), []
    )
    await manager.async_initialize()
    person = await manager.async_create_person(
        name='Hello',
        user_id=hass_read_only_user.id
    )

    await hass.auth.async_remove_user(hass_read_only_user)
    await hass.async_block_till_done()
    assert person['user_id'] is None
