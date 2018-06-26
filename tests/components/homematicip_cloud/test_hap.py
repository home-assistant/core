"""Test HomematicIP Cloud hap."""

from unittest.mock import Mock, patch

from homeassistant.components import homematicip_cloud as hmipc

from tests.common import mock_coro

import homematicip
from homematicip.base.base_connection import HmipConnectionError

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


async def test_hap_setup_invalid_token():
    """Test we start config flow if username is no longer whitelisted."""
    hass = Mock()
    entry = Mock()
    entry.data = {
        hmipc.HMIPC_HAPID: 'ABC123',
        hmipc.HMIPC_AUTHTOKEN: '123',
        hmipc.HMIPC_NAME: 'hmip',
    }
    hap = hmipc.HomematicipHAP(hass, entry)

    with patch.object(hap, 'get_hap',
                      side_effect=HmipConnectionError):
        assert await hap.async_setup() is False

    assert len(hass.async_add_job.mock_calls) == 0
    assert len(hass.config_entries.flow.async_init.mock_calls) == 0


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
