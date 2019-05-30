"""Test Zeroconf component setup process."""
from unittest.mock import patch

from zeroconf import ServiceInfo, ServiceStateChange

from homeassistant.generated import zeroconf as zc_gen
from homeassistant.setup import async_setup_component
from homeassistant.components import zeroconf


def service_update_mock(zeroconf, service, handlers):
    """Call service update handler."""
    handlers[0](
        zeroconf, service, '{}.{}'.format('name', service),
        ServiceStateChange.Added)


def get_service_info_mock(service_type, name):
    """Return service info for get_service_info."""
    return ServiceInfo(
        service_type, name, address=b'\n\x00\x00\x14', port=80, weight=0,
        priority=0, server='name.local.',
        properties={b'macaddress': b'ABCDEF012345'})


async def test_setup(hass):
    """Test configured options for a device are loaded via config entry."""
    with patch.object(hass.config_entries, 'flow'), \
            patch.object(zeroconf, 'ServiceBrowser') as MockServiceBrowser, \
            patch.object(zeroconf.Zeroconf, 'get_service_info'):

        assert await async_setup_component(
            hass, zeroconf.DOMAIN, {zeroconf.DOMAIN: {}})

    assert len(MockServiceBrowser.mock_calls) == len(zc_gen.ZEROCONF)
