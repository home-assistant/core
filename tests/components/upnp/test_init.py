"""Test UPnP/IGD setup process."""

from ipaddress import ip_address
from unittest.mock import patch, MagicMock

from homeassistant.setup import async_setup_component
from homeassistant.components import upnp
from homeassistant.components.upnp.device import Device
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

from tests.common import MockConfigEntry
from tests.common import MockDependency
from tests.common import mock_coro


class MockDevice(Device):
    """Mock device for Device."""

    def __init__(self, udn):
        """Initializer."""
        super().__init__(MagicMock())
        self._udn = udn
        self.added_port_mappings = []
        self.removed_port_mappings = []

    @classmethod
    async def async_create_device(cls, hass, ssdp_description):
        """Return self."""
        return cls('UDN')

    @property
    def udn(self):
        """Get the UDN."""
        return self._udn

    async def _async_add_port_mapping(self,
                                      external_port,
                                      local_ip,
                                      internal_port):
        """Add a port mapping."""
        entry = [external_port, local_ip, internal_port]
        self.added_port_mappings.append(entry)

    async def _async_delete_port_mapping(self, external_port):
        """Remove a port mapping."""
        entry = external_port
        self.removed_port_mappings.append(entry)


async def test_async_setup_entry_default(hass):
    """Test async_setup_entry."""
    udn = 'uuid:device_1'
    entry = MockConfigEntry(domain=upnp.DOMAIN)

    config = {
        'http': {},
        'discovery': {},
        # no upnp
    }
    with MockDependency('netdisco.discovery'), \
        patch('homeassistant.components.upnp.get_local_ip',
              return_value='192.168.1.10'):
        await async_setup_component(hass, 'http', config)
        await async_setup_component(hass, 'upnp', config)
        await hass.async_block_till_done()

    # mock homeassistant.components.upnp.device.Device
    mock_device = MockDevice(udn)
    discovery_infos = [{
        'udn': udn,
        'ssdp_description': 'http://192.168.1.1/desc.xml',
    }]
    with patch.object(Device, 'async_create_device') as create_device, \
         patch.object(Device, 'async_discover') as async_discover:  # noqa:E125

        create_device.return_value = mock_coro(return_value=mock_device)
        async_discover.return_value = mock_coro(return_value=discovery_infos)

        assert await upnp.async_setup_entry(hass, entry) is True

        # ensure device is stored/used
        assert hass.data[upnp.DOMAIN]['devices'][udn] == mock_device

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    # ensure no port-mappings created or removed
    assert not mock_device.added_port_mappings
    assert not mock_device.removed_port_mappings


async def test_async_setup_entry_port_mapping(hass):
    """Test async_setup_entry."""
    # pylint: disable=invalid-name
    udn = 'uuid:device_1'
    entry = MockConfigEntry(domain=upnp.DOMAIN)

    config = {
        'http': {},
        'discovery': {},
        'upnp': {
            'port_mapping': True,
            'ports': {'hass': 'hass'},
        },
    }
    with MockDependency('netdisco.discovery'), \
        patch('homeassistant.components.upnp.get_local_ip',
              return_value='192.168.1.10'):
        await async_setup_component(hass, 'http', config)
        await async_setup_component(hass, 'upnp', config)
        await hass.async_block_till_done()

    mock_device = MockDevice(udn)
    discovery_infos = [{
        'udn': udn,
        'ssdp_description': 'http://192.168.1.1/desc.xml',
    }]
    with patch.object(Device, 'async_create_device') as create_device, \
         patch.object(Device, 'async_discover') as async_discover:  # noqa:E125

        create_device.return_value = mock_coro(return_value=mock_device)
        async_discover.return_value = mock_coro(return_value=discovery_infos)

        assert await upnp.async_setup_entry(hass, entry) is True

        # ensure device is stored/used
        assert hass.data[upnp.DOMAIN]['devices'][udn] == mock_device

        # ensure add-port-mapping-methods called
        assert mock_device.added_port_mappings == [
            [8123, ip_address('192.168.1.10'), 8123]
        ]

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    # ensure delete-port-mapping-methods called
    assert mock_device.removed_port_mappings == [8123]
