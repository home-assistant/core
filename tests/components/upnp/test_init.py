"""Test UPnP/IGD setup process."""

from ipaddress import ip_address
from unittest.mock import patch, MagicMock

from homeassistant.setup import async_setup_component
from homeassistant.components import upnp
from homeassistant.components.upnp.device import Device
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

from tests.common import MockConfigEntry
from tests.common import mock_coro


class MockDevice(Device):
    """Mock device for Device."""

    def __init__(self, udn):
        """Initializer."""
        super().__init__(None)
        self._udn = udn
        self.added_port_mappings = []
        self.removed_port_mappings = []

    @classmethod
    async def async_create_device(cls, hass, ssdp_description):
        """Return self."""
        return cls()

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


async def test_async_setup_no_auto_config(hass):
    """Test async_setup."""
    # setup component, enable auto_config
    await async_setup_component(hass, 'upnp')

    assert hass.data[upnp.DOMAIN]['auto_config'] == {
        'active': False,
        'enable_sensors': False,
        'enable_port_mapping': False,
        'ports': {'hass': 'hass'},
    }


async def test_async_setup_auto_config(hass):
    """Test async_setup."""
    # setup component, enable auto_config
    await async_setup_component(hass, 'upnp', {'upnp': {}, 'discovery': {}})

    assert hass.data[upnp.DOMAIN]['auto_config'] == {
        'active': True,
        'enable_sensors': True,
        'enable_port_mapping': False,
        'ports': {'hass': 'hass'},
    }


async def test_async_setup_auto_config_port_mapping(hass):
    """Test async_setup."""
    # setup component, enable auto_config
    await async_setup_component(hass, 'upnp', {
        'upnp': {
            'port_mapping': True,
            'ports': {'hass': 'hass'},
        },
        'discovery': {}})

    assert hass.data[upnp.DOMAIN]['auto_config'] == {
        'active': True,
        'enable_sensors': True,
        'enable_port_mapping': True,
        'ports': {'hass': 'hass'},
    }


async def test_async_setup_auto_config_no_sensors(hass):
    """Test async_setup."""
    # setup component, enable auto_config
    await async_setup_component(hass, 'upnp', {
        'upnp': {'sensors': False},
        'discovery': {}})

    assert hass.data[upnp.DOMAIN]['auto_config'] == {
        'active': True,
        'enable_sensors': False,
        'enable_port_mapping': False,
        'ports': {'hass': 'hass'},
    }


async def test_async_setup_entry_default(hass):
    """Test async_setup_entry."""
    udn = 'uuid:device_1'
    entry = MockConfigEntry(domain=upnp.DOMAIN, data={
        'ssdp_description': 'http://192.168.1.1/desc.xml',
        'udn': udn,
        'sensors': True,
        'port_mapping': False,
    })

    # ensure hass.http is available
    await async_setup_component(hass, 'upnp')

    # mock homeassistant.components.upnp.device.Device
    mock_device = MagicMock()
    mock_device.udn = udn
    mock_device.async_add_port_mappings.return_value = mock_coro()
    mock_device.async_delete_port_mappings.return_value = mock_coro()
    with patch.object(Device, 'async_create_device') as mock_create_device:
        mock_create_device.return_value = mock_coro(
            return_value=mock_device)
        with patch('homeassistant.components.upnp.device.get_local_ip',
                   return_value='192.168.1.10'):
            assert await upnp.async_setup_entry(hass, entry) is True

            # ensure device is stored/used
            assert hass.data[upnp.DOMAIN]['devices'][udn] == mock_device

            hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
            await hass.async_block_till_done()

    # ensure cleaned up
    assert udn not in hass.data[upnp.DOMAIN]['devices']

    # ensure no port-mapping-methods called
    assert len(mock_device.async_add_port_mappings.mock_calls) == 0
    assert len(mock_device.async_delete_port_mappings.mock_calls) == 0


async def test_async_setup_entry_port_mapping(hass):
    """Test async_setup_entry."""
    udn = 'uuid:device_1'
    entry = MockConfigEntry(domain=upnp.DOMAIN, data={
        'ssdp_description': 'http://192.168.1.1/desc.xml',
        'udn': udn,
        'sensors': False,
        'port_mapping': True,
    })

    # ensure hass.http is available
    await async_setup_component(hass, 'upnp', {
        'upnp': {
            'port_mapping': True,
            'ports': {'hass': 'hass'},
        },
        'discovery': {},
    })

    mock_device = MockDevice(udn)
    with patch.object(Device, 'async_create_device') as mock_create_device:
        mock_create_device.return_value = mock_coro(return_value=mock_device)
        with patch('homeassistant.components.upnp.device.get_local_ip',
                   return_value='192.168.1.10'):
            assert await upnp.async_setup_entry(hass, entry) is True

            # ensure device is stored/used
            assert hass.data[upnp.DOMAIN]['devices'][udn] == mock_device

            # ensure add-port-mapping-methods called
            assert mock_device.added_port_mappings == [
                [8123, ip_address('192.168.1.10'), 8123]
            ]

            hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
            await hass.async_block_till_done()

    # ensure cleaned up
    assert udn not in hass.data[upnp.DOMAIN]['devices']

    # ensure delete-port-mapping-methods called
    assert mock_device.removed_port_mappings == [8123]
