"""Test entity_registry API."""
import pytest

from homeassistant.setup import async_setup_component
from homeassistant.helpers.entity_registry import RegistryEntry
from homeassistant.components.config import entity_registry
from tests.common import mock_registry, MockEntity, MockEntityPlatform


@pytest.fixture
def client(hass, test_client):
    """Fixture that can interact with the config manager API."""
    hass.loop.run_until_complete(async_setup_component(hass, 'http', {}))
    hass.loop.run_until_complete(entity_registry.async_setup(hass))
    yield hass.loop.run_until_complete(test_client(hass.http.app))


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

    resp = await client.get(
        '/api/config/entity_registry/test_domain.name')
    assert resp.status == 200
    data = await resp.json()
    assert data == {
        'entity_id': 'test_domain.name',
        'name': 'Hello World'
    }

    resp = await client.get(
        '/api/config/entity_registry/test_domain.no_name')
    assert resp.status == 200
    data = await resp.json()
    assert data == {
        'entity_id': 'test_domain.no_name',
        'name': None
    }


async def test_update_entity(hass, client):
    """Test get entry."""
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

    resp = await client.post(
        '/api/config/entity_registry/test_domain.world', json={
            'name': 'after update'
        })
    assert resp.status == 200
    data = await resp.json()
    assert data == {
        'entity_id': 'test_domain.world',
        'name': 'after update'
    }

    state = hass.states.get('test_domain.world')
    assert state.name == 'after update'


async def test_update_entity_no_changes(hass, client):
    """Test get entry."""
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

    resp = await client.post(
        '/api/config/entity_registry/test_domain.world', json={
            'name': 'name of entity'
        })
    assert resp.status == 200
    data = await resp.json()
    assert data == {
        'entity_id': 'test_domain.world',
        'name': 'name of entity'
    }

    state = hass.states.get('test_domain.world')
    assert state.name == 'name of entity'


async def test_get_nonexisting_entity(client):
    """Test get entry."""
    resp = await client.get(
        '/api/config/entity_registry/test_domain.non_existing')
    assert resp.status == 404


async def test_update_nonexisting_entity(client):
    """Test get entry."""
    resp = await client.post(
        '/api/config/entity_registry/test_domain.non_existing', json={
            'name': 'some name'
        })
    assert resp.status == 404
