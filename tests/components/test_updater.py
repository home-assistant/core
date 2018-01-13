"""The tests for the Updater component."""
import asyncio
from datetime import timedelta
from unittest.mock import patch, Mock

import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components import updater
import homeassistant.util.dt as dt_util
from tests.common import async_fire_time_changed, mock_coro, mock_component

NEW_VERSION = '10000.0'
MOCK_VERSION = '10.0'
MOCK_DEV_VERSION = '10.0.dev0'
MOCK_HUUID = 'abcdefg'
MOCK_RESPONSE = {
    'version': '0.15',
    'release-notes': 'https://home-assistant.io'
}
MOCK_CONFIG = {updater.DOMAIN: {
    'reporting': True
}}


@pytest.fixture
def mock_get_newest_version():
    """Fixture to mock get_newest_version."""
    with patch('homeassistant.components.updater.get_newest_version') as mock:
        yield mock


@pytest.fixture
def mock_get_uuid():
    """Fixture to mock get_uuid."""
    with patch('homeassistant.components.updater._load_uuid') as mock:
        yield mock


@asyncio.coroutine
def test_new_version_shows_entity_after_hour(
        hass, mock_get_uuid, mock_get_newest_version):
    """Test if new entity is created if new version is available."""
    mock_get_uuid.return_value = MOCK_HUUID
    mock_get_newest_version.return_value = mock_coro((NEW_VERSION, ''))

    res = yield from async_setup_component(
        hass, updater.DOMAIN, {updater.DOMAIN: {}})
    assert res, 'Updater failed to setup'

    with patch('homeassistant.components.updater.current_version',
               MOCK_VERSION):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1))
        yield from hass.async_block_till_done()

    assert hass.states.is_state(updater.ENTITY_ID, NEW_VERSION)


@asyncio.coroutine
def test_same_version_not_show_entity(
        hass, mock_get_uuid, mock_get_newest_version):
    """Test if new entity is created if new version is available."""
    mock_get_uuid.return_value = MOCK_HUUID
    mock_get_newest_version.return_value = mock_coro((MOCK_VERSION, ''))

    res = yield from async_setup_component(
        hass, updater.DOMAIN, {updater.DOMAIN: {}})
    assert res, 'Updater failed to setup'

    with patch('homeassistant.components.updater.current_version',
               MOCK_VERSION):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1))
        yield from hass.async_block_till_done()

    assert hass.states.get(updater.ENTITY_ID) is None


@asyncio.coroutine
def test_disable_reporting(hass, mock_get_uuid, mock_get_newest_version):
    """Test if new entity is created if new version is available."""
    mock_get_uuid.return_value = MOCK_HUUID
    mock_get_newest_version.return_value = mock_coro((MOCK_VERSION, ''))

    res = yield from async_setup_component(
        hass, updater.DOMAIN, {updater.DOMAIN: {
            'reporting': False
        }})
    assert res, 'Updater failed to setup'

    with patch('homeassistant.components.updater.current_version',
               MOCK_VERSION):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1))
        yield from hass.async_block_till_done()

    assert hass.states.get(updater.ENTITY_ID) is None
    res = yield from updater.get_newest_version(hass, MOCK_HUUID, MOCK_CONFIG)
    call = mock_get_newest_version.mock_calls[0][1]
    assert call[0] is hass
    assert call[1] is None


@asyncio.coroutine
def test_enabled_component_info(hass, mock_get_uuid):
    """Test if new entity is created if new version is available."""
    with patch('homeassistant.components.updater.platform.system',
               Mock(return_value="junk")):
        res = yield from updater.get_system_info(hass, True)
        assert 'components' in res, 'Updater failed to generate component list'


@asyncio.coroutine
def test_disable_component_info(hass, mock_get_uuid):
    """Test if new entity is created if new version is available."""
    with patch('homeassistant.components.updater.platform.system',
               Mock(return_value="junk")):
        res = yield from updater.get_system_info(hass, False)
        assert 'components' not in res, 'Updater failed, components generate'


@asyncio.coroutine
def test_get_newest_version_no_analytics_when_no_huuid(hass, aioclient_mock):
    """Test we do not gather analytics when no huuid is passed in."""
    aioclient_mock.post(updater.UPDATER_URL, json=MOCK_RESPONSE)

    with patch('homeassistant.components.updater.get_system_info',
               side_effect=Exception):
        res = yield from updater.get_newest_version(hass, None, False)
        assert res == (MOCK_RESPONSE['version'],
                       MOCK_RESPONSE['release-notes'])


@asyncio.coroutine
def test_get_newest_version_analytics_when_huuid(hass, aioclient_mock):
    """Test we do not gather analytics when no huuid is passed in."""
    aioclient_mock.post(updater.UPDATER_URL, json=MOCK_RESPONSE)

    with patch('homeassistant.components.updater.get_system_info',
               Mock(return_value=mock_coro({'fake': 'bla'}))):
        res = yield from updater.get_newest_version(hass, MOCK_HUUID, False)
        assert res == (MOCK_RESPONSE['version'],
                       MOCK_RESPONSE['release-notes'])


@asyncio.coroutine
def test_error_fetching_new_version_timeout(hass):
    """Test we do not gather analytics when no huuid is passed in."""
    with patch('homeassistant.components.updater.get_system_info',
               Mock(return_value=mock_coro({'fake': 'bla'}))), \
            patch('async_timeout.timeout', side_effect=asyncio.TimeoutError):
        res = yield from updater.get_newest_version(hass, MOCK_HUUID, False)
        assert res is None


@asyncio.coroutine
def test_error_fetching_new_version_bad_json(hass, aioclient_mock):
    """Test we do not gather analytics when no huuid is passed in."""
    aioclient_mock.post(updater.UPDATER_URL, text='not json')

    with patch('homeassistant.components.updater.get_system_info',
               Mock(return_value=mock_coro({'fake': 'bla'}))):
        res = yield from updater.get_newest_version(hass, MOCK_HUUID, False)
        assert res is None


@asyncio.coroutine
def test_error_fetching_new_version_invalid_response(hass, aioclient_mock):
    """Test we do not gather analytics when no huuid is passed in."""
    aioclient_mock.post(updater.UPDATER_URL, json={
        'version': '0.15'
        # 'release-notes' is missing
    })

    with patch('homeassistant.components.updater.get_system_info',
               Mock(return_value=mock_coro({'fake': 'bla'}))):
        res = yield from updater.get_newest_version(hass, MOCK_HUUID, False)
        assert res is None


@asyncio.coroutine
def test_new_version_shows_entity_after_hour_hassio(
        hass, mock_get_uuid, mock_get_newest_version):
    """Test if new entity is created if new version is available / hass.io."""
    mock_get_uuid.return_value = MOCK_HUUID
    mock_get_newest_version.return_value = mock_coro((NEW_VERSION, ''))
    mock_component(hass, 'hassio')
    hass.data['hassio_hass_version'] = "999.0"

    res = yield from async_setup_component(
        hass, updater.DOMAIN, {updater.DOMAIN: {}})
    assert res, 'Updater failed to setup'

    with patch('homeassistant.components.updater.current_version',
               MOCK_VERSION):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=1))
        yield from hass.async_block_till_done()

    assert hass.states.is_state(updater.ENTITY_ID, "999.0")
