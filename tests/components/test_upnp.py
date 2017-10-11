"""Test the UPNP component."""
import asyncio
from collections import OrderedDict
from unittest.mock import patch, MagicMock

import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_miniupnpc():
    """Mock miniupnpc."""
    mock = MagicMock()

    with patch.dict('sys.modules', {'miniupnpc': mock}):
        yield mock.UPnP()


@pytest.fixture
def mock_local_ip():
    """Mock get_local_ip."""
    with patch('homeassistant.components.upnp.get_local_ip',
               return_value='192.168.0.10'):
        yield


@pytest.fixture(autouse=True)
def mock_discovery():
    """Mock discovery of upnp sensor."""
    with patch('homeassistant.components.upnp.discovery'):
        yield


@asyncio.coroutine
def test_setup_fail_if_no_ip(hass):
    """Test setup fails if we can't find a local IP."""
    with patch('homeassistant.components.upnp.get_local_ip',
               return_value='127.0.0.1'):
        result = yield from async_setup_component(hass, 'upnp', {
            'upnp': {}
        })

    assert not result


@asyncio.coroutine
def test_setup_fail_if_cannot_select_igd(hass, mock_local_ip, mock_miniupnpc):
    """Test setup fails if we can't find an UPnP IGD."""
    mock_miniupnpc.selectigd.side_effect = Exception

    result = yield from async_setup_component(hass, 'upnp', {
        'upnp': {}
    })

    assert not result


@asyncio.coroutine
def test_setup_succeeds_if_specify_ip(hass, mock_miniupnpc):
    """Test setup succeeds if we specify IP and can't find a local IP."""
    with patch('homeassistant.components.upnp.get_local_ip',
               return_value='127.0.0.1'):
        result = yield from async_setup_component(hass, 'upnp', {
            'upnp': {
                'local_ip': '192.168.0.10'
            }
        })

    assert result


@asyncio.coroutine
def test_no_config_maps_hass_local_to_remote_port(hass, mock_miniupnpc):
    """Test by default we map local to remote port."""
    result = yield from async_setup_component(hass, 'upnp', {
        'upnp': {
            'local_ip': '192.168.0.10'
        }
    })

    assert result
    assert len(mock_miniupnpc.addportmapping.mock_calls) == 1
    external, _, host, internal, _, _ = \
        mock_miniupnpc.addportmapping.mock_calls[0][1]
    assert host == '192.168.0.10'
    assert external == 8123
    assert internal == 8123


@asyncio.coroutine
def test_map_hass_to_remote_port(hass, mock_miniupnpc):
    """Test mapping hass to remote port."""
    result = yield from async_setup_component(hass, 'upnp', {
        'upnp': {
            'local_ip': '192.168.0.10',
            'ports': {
                'hass': 1000
            }
        }
    })

    assert result
    assert len(mock_miniupnpc.addportmapping.mock_calls) == 1
    external, _, host, internal, _, _ = \
        mock_miniupnpc.addportmapping.mock_calls[0][1]
    assert external == 1000
    assert internal == 8123


@asyncio.coroutine
def test_map_internal_to_remote_ports(hass, mock_miniupnpc):
    """Test mapping local to remote ports."""
    ports = OrderedDict()
    ports['hass'] = 1000
    ports[1883] = 3883

    result = yield from async_setup_component(hass, 'upnp', {
        'upnp': {
            'local_ip': '192.168.0.10',
            'ports': ports
        }
    })

    assert result
    assert len(mock_miniupnpc.addportmapping.mock_calls) == 2
    external, _, host, internal, _, _ = \
        mock_miniupnpc.addportmapping.mock_calls[0][1]
    assert external == 1000
    assert internal == 8123

    external, _, host, internal, _, _ = \
        mock_miniupnpc.addportmapping.mock_calls[1][1]
    assert external == 3883
    assert internal == 1883

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    yield from hass.async_block_till_done()
    assert len(mock_miniupnpc.deleteportmapping.mock_calls) == 2
    assert mock_miniupnpc.deleteportmapping.mock_calls[0][1][0] == 1000
    assert mock_miniupnpc.deleteportmapping.mock_calls[1][1][0] == 3883
