"""Test the UPNP component."""
from collections import OrderedDict
from unittest.mock import patch, MagicMock

import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.setup import async_setup_component
from homeassistant.components.upnp import IP_SERVICE, DATA_UPNP


class MockService(MagicMock):
    """Mock upnp IP service."""

    async def add_port_mapping(self, *args, **kwargs):
        """Original function."""
        self.mock_add_port_mapping(*args, **kwargs)

    async def delete_port_mapping(self, *args, **kwargs):
        """Original function."""
        self.mock_delete_port_mapping(*args, **kwargs)


class MockDevice(MagicMock):
    """Mock upnp device."""

    def find_first_service(self, *args, **kwargs):
        """Original function."""
        self._service = MockService()
        return self._service

    def peep_first_service(self):
        """Access Mock first service."""
        return self._service


class MockResp(MagicMock):
    """Mock upnp msearch response."""

    async def get_device(self, *args, **kwargs):
        """Original function."""
        device = MockDevice()
        service = {'serviceType': IP_SERVICE}
        device.services = [service]
        return device


@pytest.fixture
def mock_msearch_first(*args, **kwargs):
    """Wrapper to async mock function."""
    async def async_mock_msearch_first(*args, **kwargs):
        """Mock msearch_first."""
        return MockResp(*args, **kwargs)

    with patch('pyupnp_async.msearch_first', new=async_mock_msearch_first):
        yield


@pytest.fixture
def mock_async_exception(*args, **kwargs):
    """Wrapper to async mock function with exception."""
    async def async_mock_exception(*args, **kwargs):
        return Exception

    with patch('pyupnp_async.msearch_first', new=async_mock_exception):
        yield


@pytest.fixture
def mock_local_ip():
    """Mock get_local_ip."""
    with patch('homeassistant.components.upnp.get_local_ip',
               return_value='192.168.0.10'):
        yield


async def test_setup_fail_if_no_ip(hass):
    """Test setup fails if we can't find a local IP."""
    with patch('homeassistant.components.upnp.get_local_ip',
               return_value='127.0.0.1'):
        result = await async_setup_component(hass, 'upnp', {
            'upnp': {}
        })

    assert not result


async def test_setup_fail_if_cannot_select_igd(hass,
                                               mock_local_ip,
                                               mock_async_exception):
    """Test setup fails if we can't find an UPnP IGD."""
    result = await async_setup_component(hass, 'upnp', {
        'upnp': {}
    })

    assert not result


async def test_setup_succeeds_if_specify_ip(hass, mock_msearch_first):
    """Test setup succeeds if we specify IP and can't find a local IP."""
    with patch('homeassistant.components.upnp.get_local_ip',
               return_value='127.0.0.1'):
        result = await async_setup_component(hass, 'upnp', {
            'upnp': {
                'local_ip': '192.168.0.10'
            }
        })

    assert result
    mock_service = hass.data[DATA_UPNP].peep_first_service()
    assert len(mock_service.mock_add_port_mapping.mock_calls) == 1
    mock_service.mock_add_port_mapping.assert_called_once_with(
        8123, 8123, '192.168.0.10', 'TCP', desc='Home Assistant')


async def test_no_config_maps_hass_local_to_remote_port(hass,
                                                        mock_local_ip,
                                                        mock_msearch_first):
    """Test by default we map local to remote port."""
    result = await async_setup_component(hass, 'upnp', {
        'upnp': {}
    })

    assert result
    mock_service = hass.data[DATA_UPNP].peep_first_service()
    assert len(mock_service.mock_add_port_mapping.mock_calls) == 1
    mock_service.mock_add_port_mapping.assert_called_once_with(
        8123, 8123, '192.168.0.10', 'TCP', desc='Home Assistant')


async def test_map_hass_to_remote_port(hass,
                                       mock_local_ip,
                                       mock_msearch_first):
    """Test mapping hass to remote port."""
    result = await async_setup_component(hass, 'upnp', {
        'upnp': {
            'ports': {
                'hass': 1000
            }
        }
    })

    assert result
    mock_service = hass.data[DATA_UPNP].peep_first_service()
    assert len(mock_service.mock_add_port_mapping.mock_calls) == 1
    mock_service.mock_add_port_mapping.assert_called_once_with(
        8123, 1000, '192.168.0.10', 'TCP', desc='Home Assistant')


async def test_map_internal_to_remote_ports(hass,
                                            mock_local_ip,
                                            mock_msearch_first):
    """Test mapping local to remote ports."""
    ports = OrderedDict()
    ports['hass'] = 1000
    ports[1883] = 3883

    result = await async_setup_component(hass, 'upnp', {
        'upnp': {
            'ports': ports
        }
    })

    assert result
    mock_service = hass.data[DATA_UPNP].peep_first_service()
    assert len(mock_service.mock_add_port_mapping.mock_calls) == 2

    mock_service.mock_add_port_mapping.assert_any_call(
        8123, 1000, '192.168.0.10', 'TCP', desc='Home Assistant')
    mock_service.mock_add_port_mapping.assert_any_call(
        1883, 3883, '192.168.0.10', 'TCP', desc='Home Assistant')

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    assert len(mock_service.mock_delete_port_mapping.mock_calls) == 2

    mock_service.mock_delete_port_mapping.assert_any_call(1000, 'TCP')
    mock_service.mock_delete_port_mapping.assert_any_call(3883, 'TCP')
