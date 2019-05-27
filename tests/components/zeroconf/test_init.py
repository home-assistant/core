"""Test Zeroconf component setup process."""
from unittest.mock import patch

from aiozeroconf import ServiceInfo, ServiceStateChange

from homeassistant.setup import async_setup_component
from homeassistant.components import zeroconf


def service_update_mock(zeroconf, service, handlers):
    """Call service update handler."""
    handlers[0](
        None, service, '{}.{}'.format('name', service),
        ServiceStateChange.Added)


async def get_service_info_mock(service_type, name):
    """Return service info for get_service_info."""
    return ServiceInfo(
        service_type, name, address=b'\n\x00\x00\x14', port=80, weight=0,
        priority=0, server='name.local.',
        properties={b'macaddress': b'ABCDEF012345'})


async def test_setup(hass):
    """Test configured options for a device are loaded via config entry."""
    with patch.object(hass.config_entries, 'flow') as mock_config_flow, \
            patch.object(zeroconf, 'ServiceBrowser') as MockServiceBrowser, \
            patch.object(zeroconf.Zeroconf, 'get_service_info') as \
            mock_get_service_info:

        MockServiceBrowser.side_effect = service_update_mock
        mock_get_service_info.side_effect = get_service_info_mock

        assert await async_setup_component(
            hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})
        await hass.async_block_till_done()

    assert len(MockServiceBrowser.mock_calls) == 2
    assert len(mock_config_flow.mock_calls) == 2
