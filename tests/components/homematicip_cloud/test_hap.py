"""Test HomematicIP Cloud accesspoint."""
from unittest.mock import Mock, patch

from homeassistant.components.homematicip_cloud import hap as hmipc
from homeassistant.components.homematicip_cloud import const, errors
from tests.common import mock_coro


async def test_auth_setup(hass):
    """Test auth setup for client registration."""
    config = {
        const.HMIPC_HAPID: 'ABC123',
        const.HMIPC_PIN: '123',
        const.HMIPC_NAME: 'hmip',
    }
    hap = hmipc.HomematicipAuth(hass, config)
    with patch.object(hap, 'get_auth', return_value=mock_coro()):
        assert await hap.async_setup() is True


async def test_auth_setup_connection_error(hass):
    """Test auth setup connection error behaviour."""
    config = {
        const.HMIPC_HAPID: 'ABC123',
        const.HMIPC_PIN: '123',
        const.HMIPC_NAME: 'hmip',
    }
    hap = hmipc.HomematicipAuth(hass, config)
    with patch.object(hap, 'get_auth',
                      side_effect=errors.HmipcConnectionError):
        assert await hap.async_setup() is False


async def test_auth_auth_check_and_register(hass):
    """Test auth client registration."""
    config = {
        const.HMIPC_HAPID: 'ABC123',
        const.HMIPC_PIN: '123',
        const.HMIPC_NAME: 'hmip',
    }
    hap = hmipc.HomematicipAuth(hass, config)
    hap.auth = Mock()
    with patch.object(hap.auth, 'isRequestAcknowledged',
                      return_value=mock_coro()), \
            patch.object(hap.auth, 'requestAuthToken',
                         return_value=mock_coro('ABC')), \
            patch.object(hap.auth, 'confirmAuthToken',
                         return_value=mock_coro()):
        assert await hap.async_checkbutton() is True
        assert await hap.async_register() == 'ABC'


async def test_hap_setup_works(aioclient_mock):
    """Test a successful setup of a accesspoint."""
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
    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 6
    assert hass.config_entries.async_forward_entry_setup.mock_calls[0][1] == \
        (entry, 'alarm_control_panel')
    assert hass.config_entries.async_forward_entry_setup.mock_calls[1][1] == \
        (entry, 'binary_sensor')


async def test_hap_setup_connection_error():
    """Test a failed accesspoint setup."""
    hass = Mock()
    entry = Mock()
    entry.data = {
        hmipc.HMIPC_HAPID: 'ABC123',
        hmipc.HMIPC_AUTHTOKEN: '123',
        hmipc.HMIPC_NAME: 'hmip',
    }
    hap = hmipc.HomematicipHAP(hass, entry)
    with patch.object(hap, 'get_hap',
                      side_effect=errors.HmipcConnectionError):
        assert await hap.async_setup() is False

    assert len(hass.async_add_job.mock_calls) == 0
    assert len(hass.config_entries.flow.async_init.mock_calls) == 0


async def test_hap_reset_unloads_entry_if_setup():
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
    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 6

    hass.config_entries.async_forward_entry_unload.return_value = \
        mock_coro(True)
    await hap.async_reset()

    assert len(hass.config_entries.async_forward_entry_unload.mock_calls) == 6
