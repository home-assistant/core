"""Test IGD setup process."""

from unittest.mock import patch, MagicMock

from homeassistant.setup import async_setup_component
from homeassistant.components import igd
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

from tests.common import MockConfigEntry
from tests.common import mock_coro


async def test_async_setup_no_auto_config(hass):
    """Test async_setup."""
    # setup component, enable auto_config
    await async_setup_component(hass, 'igd')

    assert hass.data[igd.DOMAIN]['auto_config'] == {
        'active': False,
        'port_forward': False,
        'sensors': False,
    }


async def test_async_setup_auto_config(hass):
    """Test async_setup."""
    # setup component, enable auto_config
    await async_setup_component(hass, 'igd', {'igd': {}, 'discovery': {}})

    assert hass.data[igd.DOMAIN]['auto_config'] == {
        'active': True,
        'port_forward': False,
        'sensors': True,
    }


async def test_async_setup_auto_config_port_forward(hass):
    """Test async_setup."""
    # setup component, enable auto_config
    await async_setup_component(hass, 'igd', {
        'igd': {'port_forward': True},
        'discovery': {}})

    assert hass.data[igd.DOMAIN]['auto_config'] == {
        'active': True,
        'port_forward': True,
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

    # mock async_upnp_client.igd.IgdDevice
    mock_igd_device = MagicMock()
    mock_igd_device.udn = udn
    mock_igd_device.async_add_port_mapping.return_value = mock_coro()
    mock_igd_device.async_delete_port_mapping.return_value = mock_coro()
    with patch.object(igd, '_async_create_igd_device') as mock_create_device:
        mock_create_device.return_value = mock_coro(
            return_value=mock_igd_device)
        with patch('homeassistant.components.igd.get_local_ip',
                   return_value='192.168.1.10'):
            assert await igd.async_setup_entry(hass, entry) is True

            # ensure device is stored/used
            assert hass.data[igd.DOMAIN]['devices'][udn] == mock_igd_device

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert udn not in hass.data[igd.DOMAIN]['devices']
    assert len(mock_igd_device.async_add_port_mapping.mock_calls) == 0
    assert len(mock_igd_device.async_delete_port_mapping.mock_calls) == 0


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
    await async_setup_component(hass, 'igd')

    mock_igd_device = MagicMock()
    mock_igd_device.udn = udn
    mock_igd_device.async_add_port_mapping.return_value = mock_coro()
    mock_igd_device.async_delete_port_mapping.return_value = mock_coro()
    with patch.object(igd, '_async_create_igd_device') as mock_create_device:
        mock_create_device.return_value = mock_coro(
            return_value=mock_igd_device)
        with patch('homeassistant.components.igd.get_local_ip',
                   return_value='192.168.1.10'):
            assert await igd.async_setup_entry(hass, entry) is True

            # ensure device is stored/used
            assert hass.data[igd.DOMAIN]['devices'][udn] == mock_igd_device

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()

    assert udn not in hass.data[igd.DOMAIN]['devices']
    assert len(mock_igd_device.async_add_port_mapping.mock_calls) > 0
    assert len(mock_igd_device.async_delete_port_mapping.mock_calls) > 0
