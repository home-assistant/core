"""Test HomematicIP Cloud hap."""

from unittest.mock import Mock, patch

from homeassistant.components import homematicip_cloud as hmipc

from tests.common import mock_coro


async def test_hap_init(aioclient_mock):
    """Test a successful setup."""
    hass = Mock()
    entry = Mock()
    home = Mock()
    entry.data = {
        hmipc.HMIPC_HAPID: 'ABC123',
        hmipc.HMIPC_AUTHTOKEN: '123',
        hmipc.HMIPC_NAME: 'hmip',
    }
    hap = hmipc.HomematicipHAP(hass, entry)
    with patch.object(hap, 'get_hap', return_value=mock_coro(home)):
        assert await hap.async_setup() is True

    assert hap.home is home
    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 5
    assert hass.config_entries.async_forward_entry_setup.mock_calls[0][1] == \
        (entry, 'binary_sensor')


async def test_reset_unloads_entry_if_setup():
    """Test calling reset while the entry has been setup."""
    hass = Mock()
    entry = Mock()
    home = Mock()
    entry.data = {
        hmipc.HMIPC_HAPID: 'ABC123',
        hmipc.HMIPC_AUTHTOKEN: '123',
        hmipc.HMIPC_NAME: 'hmip',
    }
    hap = hmipc.HomematicipHAP(hass, entry)
    with patch.object(hap, 'get_hap', return_value=mock_coro(home)):
        assert await hap.async_setup() is True

    assert hap.home is home
    assert len(hass.services.async_register.mock_calls) == 0
    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 5

    hass.config_entries.async_forward_entry_unload.return_value = \
        mock_coro(True)
    await hap.async_reset()

    assert len(hass.config_entries.async_forward_entry_unload.mock_calls) == 5
