"""Test entity_registry API."""
import pytest

from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.components.config import entity_registry
from tests.common import mock_registry, MockEntity, MockEntityPlatform


@pytest.fixture
def client(hass, hass_ws_client):
    """Fixture that can interact with the config manager API."""
    hass.loop.run_until_complete(entity_registry.async_setup(hass))
    yield hass.loop.run_until_complete(hass_ws_client(hass))


async def test_get_entity(hass, client):
    """Test get entry."""
    mock_registry(hass, {
        'test_domain.name': RegistryEntry(
            entity_id='test_domain.name',
            unique_id='1234',
            platform='test_platform',
            name='Hello World'
        ),
        'test_domain.no_name': RegistryEntry(
            entity_id='test_domain.no_name',
            unique_id='6789',
            platform='test_platform',
        ),
    })

    await client.send_json({
        'id': 5,
        'type': 'config/entity_registry/get',
        'entity_id': 'test_domain.name',
    })
    msg = await client.receive_json()

    assert msg['result'] == {
        'entity_id': 'test_domain.name',
        'name': 'Hello World'
    }

    await client.send_json({
        'id': 6,
        'type': 'config/entity_registry/get',
        'entity_id': 'test_domain.no_name',
    })
    msg = await client.receive_json()

    assert msg['result'] == {
        'entity_id': 'test_domain.no_name',
        'name': None
    }


async def test_update_entity_name(hass, client):
    """Test updating entity name."""
    mock_registry(hass, {
        'test_domain.world': RegistryEntry(
            entity_id='test_domain.world',
            unique_id='1234',
            # Using component.async_add_entities is equal to platform "domain"
            platform='test_platform',
            name='before update'
        )
    })
    platform = MockEntityPlatform(hass)
    entity = MockEntity(unique_id='1234')
    await platform.async_add_entities([entity])

    state = hass.states.get('test_domain.world')
    assert state is not None
    assert state.name == 'before update'

    await client.send_json({
        'id': 6,
        'type': 'config/entity_registry/update',
        'entity_id': 'test_domain.world',
        'name': 'after update',
    })

    msg = await client.receive_json()

    assert msg['result'] == {
        'entity_id': 'test_domain.world',
        'name': 'after update'
    }

    state = hass.states.get('test_domain.world')
    assert state.name == 'after update'


async def test_update_entity_no_changes(hass, client):
    """Test update entity with no changes."""
    mock_registry(hass, {
        'test_domain.world': RegistryEntry(
            entity_id='test_domain.world',
            unique_id='1234',
            # Using component.async_add_entities is equal to platform "domain"
            platform='test_platform',
            name='name of entity'
        )
    })
    platform = MockEntityPlatform(hass)
    entity = MockEntity(unique_id='1234')
    await platform.async_add_entities([entity])

    state = hass.states.get('test_domain.world')
    assert state is not None
    assert state.name == 'name of entity'

    await client.send_json({
        'id': 6,
        'type': 'config/entity_registry/update',
        'entity_id': 'test_domain.world',
        'name': 'name of entity',
    })

    msg = await client.receive_json()

    assert msg['result'] == {
        'entity_id': 'test_domain.world',
        'name': 'name of entity'
    }

    state = hass.states.get('test_domain.world')
    assert state.name == 'name of entity'


async def test_get_nonexisting_entity(client):
    """Test get entry with nonexisting entity."""
    await client.send_json({
        'id': 6,
        'type': 'config/entity_registry/get',
        'entity_id': 'test_domain.no_name',
    })
    msg = await client.receive_json()

    assert not msg['success']


async def test_update_nonexisting_entity(client):
    """Test update a nonexisting entity."""
    await client.send_json({
        'id': 6,
        'type': 'config/entity_registry/update',
        'entity_id': 'test_domain.no_name',
        'name': 'new-name'
    })
    msg = await client.receive_json()

    assert not msg['success']


async def test_update_entity_id(hass, client):
    """Test update entity id."""
    mock_registry(hass, {
        'test_domain.world': RegistryEntry(
            entity_id='test_domain.world',
            unique_id='1234',
            # Using component.async_add_entities is equal to platform "domain"
            platform='test_platform',
        )
    })
    platform = MockEntityPlatform(hass)
    entity = MockEntity(unique_id='1234')
    await platform.async_add_entities([entity])

    assert hass.states.get('test_domain.world') is not None

    await client.send_json({
        'id': 6,
        'type': 'config/entity_registry/update',
        'entity_id': 'test_domain.world',
        'new_entity_id': 'test_domain.planet',
    })

    msg = await client.receive_json()

    assert msg['result'] == {
        'entity_id': 'test_domain.planet',
        'name': None
    }

    assert hass.states.get('test_domain.world') is None
    assert hass.states.get('test_domain.planet') is not None
