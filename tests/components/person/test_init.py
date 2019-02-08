"""The tests for the person component."""
from homeassistant.components.person import ATTR_SOURCE, ATTR_USER_ID, DOMAIN
from homeassistant.const import (
    ATTR_ID, ATTR_LATITUDE, ATTR_LONGITUDE, STATE_UNKNOWN)
from homeassistant.core import CoreState, State
from homeassistant.setup import async_setup_component

import pytest

from tests.common import mock_component, mock_restore_cache

DEVICE_TRACKER = 'device_tracker.test_tracker'
DEVICE_TRACKER_2 = 'device_tracker.test_tracker_2'


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
                    'device_trackers': DEVICE_TRACKER
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
    user_id = hass_admin_user.id
    config = {DOMAIN: {
        'id': '1234', 'name': 'tracked person', 'user_id': user_id,
        'device_trackers': DEVICE_TRACKER}}
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
    assert state.state == 'home'
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER
    assert state.attributes.get(ATTR_USER_ID) == user_id

    hass.states.async_set(
        DEVICE_TRACKER, 'not_home',
        {ATTR_LATITUDE: 10.123456, ATTR_LONGITUDE: 11.123456})
    await hass.async_block_till_done()

    state = hass.states.get('person.tracked_person')
    assert state.state == 'not_home'
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) == 10.12346
    assert state.attributes.get(ATTR_LONGITUDE) == 11.12346
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER
    assert state.attributes.get(ATTR_USER_ID) == user_id


async def test_setup_two_trackers(hass, hass_admin_user):
    """Test set up person with two device trackers."""
    user_id = hass_admin_user.id
    config = {DOMAIN: {
        'id': '1234', 'name': 'tracked person', 'user_id': user_id,
        'device_trackers': [DEVICE_TRACKER, DEVICE_TRACKER_2]}}
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
    assert state.state == 'home'
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER
    assert state.attributes.get(ATTR_USER_ID) == user_id

    hass.states.async_set(
        DEVICE_TRACKER_2, 'not_home',
        {ATTR_LATITUDE: 12.123456, ATTR_LONGITUDE: 13.123456})
    await hass.async_block_till_done()

    state = hass.states.get('person.tracked_person')
    assert state.state == 'not_home'
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) == 12.12346
    assert state.attributes.get(ATTR_LONGITUDE) == 13.12346
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER_2
    assert state.attributes.get(ATTR_USER_ID) == user_id


async def test_restore_home_state(hass, hass_admin_user):
    """Test that the state is restored for a person on startup."""
    user_id = hass_admin_user.id
    attrs = {
        ATTR_ID: '1234', ATTR_LATITUDE: 10.12346, ATTR_LONGITUDE: 11.12346,
        ATTR_SOURCE: DEVICE_TRACKER, ATTR_USER_ID: user_id}
    state = State('person.tracked_person', 'home', attrs)
    mock_restore_cache(hass, (state, ))
    hass.state = CoreState.starting
    mock_component(hass, 'recorder')
    config = {DOMAIN: {
        'id': '1234', 'name': 'tracked person', 'user_id': user_id,
        'device_trackers': DEVICE_TRACKER}}
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
    assert await async_setup_component(hass, DOMAIN, config)

    assert len(hass.states.async_entity_ids('person')) == 1
    assert hass.states.get('person.test_user_1') is not None
    assert hass.states.get('person.test_user_2') is None


async def test_load_person_stoarge(hass, hass_admin_user, storage_setup):
    """Test set up person with one device tracker."""
    state = hass.states.get('person.tracked_person')
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) is None
    assert state.attributes.get(ATTR_USER_ID) == hass_admin_user.id

    hass.states.async_set(DEVICE_TRACKER, 'home')
    await hass.async_block_till_done()

    state = hass.states.get('person.tracked_person')
    assert state.state == 'home'
    assert state.attributes.get(ATTR_ID) == '1234'
    assert state.attributes.get(ATTR_LATITUDE) is None
    assert state.attributes.get(ATTR_LONGITUDE) is None
    assert state.attributes.get(ATTR_SOURCE) == DEVICE_TRACKER
    assert state.attributes.get(ATTR_USER_ID) == hass_admin_user.id


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
