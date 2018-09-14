"""Test IGD setup process."""

from ipaddress import ip_address
from unittest.mock import patch, MagicMock

from homeassistant.setup import async_setup_component
from homeassistant.components import igd
from homeassistant.components.igd.device import Device
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
    await async_setup_component(hass, 'igd')

    assert hass.data[igd.DOMAIN]['auto_config'] == {
        'active': False,
        'port_forward': False,
        'ports': {'hass': 'hass'},
        'sensors': False,
    }


async def test_async_setup_auto_config(hass):
    """Test async_setup."""
    # setup component, enable auto_config
    await async_setup_component(hass, 'igd', {'igd': {}, 'discovery': {}})

    assert hass.data[igd.DOMAIN]['auto_config'] == {
        'active': True,
        'port_forward': False,
        'ports': {'hass': 'hass'},
        'sensors': True,
    }


async def test_async_setup_auto_config_port_forward(hass):
    """Test async_setup."""
    # setup component, enable auto_config
    await async_setup_component(hass, 'igd', {
        'igd': {
            'port_forward': True,
            'ports': {'hass': 'hass'},
        },
        'discovery': {}})

    assert hass.data[igd.DOMAIN]['auto_config'] == {
        'active': True,
        'port_forward': True,
        'ports': {'hass': 'hass'},
        'sensors': True,
    }


async def test_async_setup_auto_config_no_sensors(hass):
    """Test async_setup."""
    # setup component, enable auto_config
    await async_setup_component(hass, 'igd', {
        'igd': {'sensors': False},
        'discovery': {}})

    assert hass.data[igd.DOMAIN]['auto_config'] == {
        'active': True,
        'port_forward': False,
        'ports': {'hass': 'hass'},
        'sensors': False,
    }


async def test_async_setup_entry_default(hass):
    """Test async_setup_entry."""
    udn = 'uuid:device_1'
    entry = MockConfigEntry(domain=igd.DOMAIN, data={
        'ssdp_description': 'http://192.168.1.1/desc.xml',
        'udn': udn,
        'sensors': True,
        'port_forward': False,
    })

    # ensure hass.http is available
    await async_setup_component(hass, 'igd')

    # mock homeassistant.components.igd.device.Device
    mock_device = MagicMock()
    mock_device.udn = udn
    mock_device.async_add_port_mappings.return_value = mock_coro()
    mock_device.async_delete_port_mappings.return_value = mock_coro()
    with patch.object(Device, 'async_create_device') as mock_create_device:
        mock_create_device.return_value = mock_coro(
            return_value=mock_device)
        with patch('homeassistant.components.igd.device.get_local_ip',
                   return_value='192.168.1.10'):
            assert await igd.async_setup_entry(hass, entry) is True

            # ensure device is stored/used
            assert hass.data[igd.DOMAIN]['devices'][udn] == mock_device

            hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
            await hass.async_block_till_done()

    # ensure cleaned up
    assert udn not in hass.data[igd.DOMAIN]['devices']

    # ensure no port-mapping-methods called
    assert len(mock_device.async_add_port_mappings.mock_calls) == 0
    assert len(mock_device.async_delete_port_mappings.mock_calls) == 0


async def test_async_setup_entry_port_forward(hass):
    """Test async_setup_entry."""
    udn = 'uuid:device_1'
    entry = MockConfigEntry(domain=igd.DOMAIN, data={
        'ssdp_description': 'http://192.168.1.1/desc.xml',
        'udn': udn,
        'sensors': False,
        'port_forward': True,
    })

    # ensure hass.http is available
    await async_setup_component(hass, 'igd', {
        'igd': {
            'port_forward': True,
            'ports': {'hass': 'hass'},
        },
        'discovery': {},
    })

    mock_device = MockDevice(udn)
    with patch.object(Device, 'async_create_device') as mock_create_device:
        mock_create_device.return_value = mock_coro(return_value=mock_device)
        with patch('homeassistant.components.igd.device.get_local_ip',
                   return_value='192.168.1.10'):
            assert await igd.async_setup_entry(hass, entry) is True

            # ensure device is stored/used
            assert hass.data[igd.DOMAIN]['devices'][udn] == mock_device

            # ensure add-port-mapping-methods called
            assert mock_device.added_port_mappings == [
                [8123, ip_address('192.168.1.10'), 8123]
            ]

            hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
            await hass.async_block_till_done()

    # ensure cleaned up
    assert udn not in hass.data[igd.DOMAIN]['devices']

    # ensure delete-port-mapping-methods called
    assert mock_device.removed_port_mappings == [8123]
