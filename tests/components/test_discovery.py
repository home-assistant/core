"""The tests for the discovery component."""
import asyncio

from unittest.mock import patch

from homeassistant.bootstrap import async_setup_component
from homeassistant.components import discovery
from homeassistant.const import EVENT_HOMEASSISTANT_START

from tests.common import mock_coro

# One might consider to "mock" services, but it's easy enough to just use
# what is already available.
SERVICE = 'yamaha'
SERVICE_COMPONENT = 'media_player'

SERVICE_NO_PLATFORM = 'hass_ios'
SERVICE_NO_PLATFORM_COMPONENT = 'ios'
SERVICE_INFO = {'key': 'value'}  # Can be anything

UNKNOWN_SERVICE = 'this_service_will_never_be_supported'

BASE_CONFIG = {
    discovery.DOMAIN: {
        'ignore': []
    }
}

IGNORE_CONFIG = {
    discovery.DOMAIN: {
        'ignore': [SERVICE_NO_PLATFORM]
    }
}


@asyncio.coroutine
def test_unknown_service(hass):
    """Test that unknown service is ignored."""
    result = yield from async_setup_component(hass, 'discovery', {
        'discovery': {},
    })
    assert result

    def discover(netdisco):
        """Fake discovery."""
        return [('this_service_will_never_be_supported', {'info': 'some'})]

    with patch.object(discovery, '_discover', discover), \
            patch('homeassistant.components.discovery.async_discover',
                  return_value=mock_coro()) as mock_discover, \
            patch('homeassistant.components.discovery.async_load_platform',
                  return_value=mock_coro()) as mock_platform:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        yield from hass.async_block_till_done()

    assert not mock_discover.called
    assert not mock_platform.called


@asyncio.coroutine
def test_load_platform(hass):
    """Test load a platform."""
    result = yield from async_setup_component(hass, 'discovery', BASE_CONFIG)
    assert result

    def discover(netdisco):
        """Fake discovery."""
        return [(SERVICE, SERVICE_INFO)]

    with patch.object(discovery, '_discover', discover), \
            patch('homeassistant.components.discovery.async_discover',
                  return_value=mock_coro()) as mock_discover, \
            patch('homeassistant.components.discovery.async_load_platform',
                  return_value=mock_coro()) as mock_platform:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        yield from hass.async_block_till_done()

    assert not mock_discover.called
    assert mock_platform.called
    mock_platform.assert_called_with(
        hass, SERVICE_COMPONENT, SERVICE, SERVICE_INFO, BASE_CONFIG)


@asyncio.coroutine
def test_load_component(hass):
    """Test load a component."""
    result = yield from async_setup_component(hass, 'discovery', BASE_CONFIG)
    assert result

    def discover(netdisco):
        """Fake discovery."""
        return [(SERVICE_NO_PLATFORM, SERVICE_INFO)]

    with patch.object(discovery, '_discover', discover), \
            patch('homeassistant.components.discovery.async_discover',
                  return_value=mock_coro()) as mock_discover, \
            patch('homeassistant.components.discovery.async_load_platform',
                  return_value=mock_coro()) as mock_platform:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        yield from hass.async_block_till_done()

    assert mock_discover.called
    assert not mock_platform.called
    mock_discover.assert_called_with(
        hass, SERVICE_NO_PLATFORM, SERVICE_INFO,
        SERVICE_NO_PLATFORM_COMPONENT, BASE_CONFIG)


@asyncio.coroutine
def test_ignore_service(hass):
    """Test ignore service."""
    result = yield from async_setup_component(hass, 'discovery', IGNORE_CONFIG)
    assert result

    def discover(netdisco):
        """Fake discovery."""
        return [(SERVICE_NO_PLATFORM, SERVICE_INFO)]

    with patch.object(discovery, '_discover', discover), \
            patch('homeassistant.components.discovery.async_discover',
                  return_value=mock_coro()) as mock_discover, \
            patch('homeassistant.components.discovery.async_load_platform',
                  return_value=mock_coro()) as mock_platform:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        yield from hass.async_block_till_done()

    assert not mock_discover.called
    assert not mock_platform.called


@asyncio.coroutine
def test_discover_duplicates(hass):
    """Test load a component."""
    result = yield from async_setup_component(hass, 'discovery', BASE_CONFIG)
    assert result

    def discover(netdisco):
        """Fake discovery."""
        return [(SERVICE_NO_PLATFORM, SERVICE_INFO),
                (SERVICE_NO_PLATFORM, SERVICE_INFO)]

    with patch.object(discovery, '_discover', discover), \
            patch('homeassistant.components.discovery.async_discover',
                  return_value=mock_coro()) as mock_discover, \
            patch('homeassistant.components.discovery.async_load_platform',
                  return_value=mock_coro()) as mock_platform:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_START)
        yield from hass.async_block_till_done()

    assert mock_discover.called
    assert mock_discover.call_count == 1
    assert not mock_platform.called
    mock_discover.assert_called_with(
        hass, SERVICE_NO_PLATFORM, SERVICE_INFO,
        SERVICE_NO_PLATFORM_COMPONENT, BASE_CONFIG)
