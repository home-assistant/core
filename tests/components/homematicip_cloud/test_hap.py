"""Test HomematicIP Cloud accesspoint."""

from asynctest import Mock, patch
from homematicip.aio.auth import AsyncAuth
from homematicip.base.base_connection import HmipConnectionError
import pytest

from homeassistant.components.homematicip_cloud import (
    DOMAIN as HMIPC_DOMAIN,
    const,
    errors,
    hap as hmipc,
)
from homeassistant.components.homematicip_cloud.hap import (
    HomematicipAuth,
    HomematicipHAP,
)
from homeassistant.exceptions import ConfigEntryNotReady

from .helper import HAPID, HAPPIN

from tests.common import mock_coro, mock_coro_func


async def test_auth_setup(hass):
    """Test auth setup for client registration."""
    config = {
        const.HMIPC_HAPID: "ABC123",
        const.HMIPC_PIN: "123",
        const.HMIPC_NAME: "hmip",
    }
    hap = hmipc.HomematicipAuth(hass, config)
    with patch.object(hap, "get_auth", return_value=mock_coro()):
        assert await hap.async_setup()


async def test_auth_setup_connection_error(hass):
    """Test auth setup connection error behaviour."""
    config = {
        const.HMIPC_HAPID: "ABC123",
        const.HMIPC_PIN: "123",
        const.HMIPC_NAME: "hmip",
    }
    hap = hmipc.HomematicipAuth(hass, config)
    with patch.object(hap, "get_auth", side_effect=errors.HmipcConnectionError):
        assert not await hap.async_setup()


async def test_auth_auth_check_and_register(hass):
    """Test auth client registration."""
    config = {
        const.HMIPC_HAPID: "ABC123",
        const.HMIPC_PIN: "123",
        const.HMIPC_NAME: "hmip",
    }
    hap = hmipc.HomematicipAuth(hass, config)
    hap.auth = Mock()
    with patch.object(
        hap.auth, "isRequestAcknowledged", return_value=mock_coro(True)
    ), patch.object(
        hap.auth, "requestAuthToken", return_value=mock_coro("ABC")
    ), patch.object(
        hap.auth, "confirmAuthToken", return_value=mock_coro()
    ):
        assert await hap.async_checkbutton()
        assert await hap.async_register() == "ABC"


async def test_auth_auth_check_and_register_with_exception(hass):
    """Test auth client registration."""
    config = {
        const.HMIPC_HAPID: "ABC123",
        const.HMIPC_PIN: "123",
        const.HMIPC_NAME: "hmip",
    }
    hap = hmipc.HomematicipAuth(hass, config)
    hap.auth = Mock(spec=AsyncAuth)
    with patch.object(
        hap.auth, "isRequestAcknowledged", side_effect=HmipConnectionError
    ), patch.object(hap.auth, "requestAuthToken", side_effect=HmipConnectionError):
        assert not await hap.async_checkbutton()
        assert await hap.async_register() is False


async def test_hap_setup_works(aioclient_mock):
    """Test a successful setup of a accesspoint."""
    hass = Mock()
    entry = Mock()
    home = Mock()
    entry.data = {
        hmipc.HMIPC_HAPID: "ABC123",
        hmipc.HMIPC_AUTHTOKEN: "123",
        hmipc.HMIPC_NAME: "hmip",
    }
    hap = hmipc.HomematicipHAP(hass, entry)
    with patch.object(hap, "get_hap", return_value=mock_coro(home)):
        assert await hap.async_setup()

    assert hap.home is home
    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 8
    assert hass.config_entries.async_forward_entry_setup.mock_calls[0][1] == (
        entry,
        "alarm_control_panel",
    )
    assert hass.config_entries.async_forward_entry_setup.mock_calls[1][1] == (
        entry,
        "binary_sensor",
    )


async def test_hap_setup_connection_error():
    """Test a failed accesspoint setup."""
    hass = Mock()
    entry = Mock()
    entry.data = {
        hmipc.HMIPC_HAPID: "ABC123",
        hmipc.HMIPC_AUTHTOKEN: "123",
        hmipc.HMIPC_NAME: "hmip",
    }
    hap = hmipc.HomematicipHAP(hass, entry)
    with patch.object(
        hap, "get_hap", side_effect=errors.HmipcConnectionError
    ), pytest.raises(ConfigEntryNotReady):
        await hap.async_setup()

    assert not hass.async_add_job.mock_calls
    assert not hass.config_entries.flow.async_init.mock_calls


async def test_hap_reset_unloads_entry_if_setup():
    """Test calling reset while the entry has been setup."""
    hass = Mock()
    entry = Mock()
    home = Mock()
    home.disable_events = mock_coro_func()
    entry.data = {
        hmipc.HMIPC_HAPID: "ABC123",
        hmipc.HMIPC_AUTHTOKEN: "123",
        hmipc.HMIPC_NAME: "hmip",
    }
    hap = hmipc.HomematicipHAP(hass, entry)
    with patch.object(hap, "get_hap", return_value=mock_coro(home)):
        assert await hap.async_setup()

    assert hap.home is home
    assert not hass.services.async_register.mock_calls
    assert len(hass.config_entries.async_forward_entry_setup.mock_calls) == 8

    hass.config_entries.async_forward_entry_unload.return_value = mock_coro(True)
    await hap.async_reset()

    assert len(hass.config_entries.async_forward_entry_unload.mock_calls) == 8


async def test_hap_create(hass, hmip_config_entry, simple_mock_home):
    """Mock AsyncHome to execute get_hap."""
    hass.config.components.add(HMIPC_DOMAIN)
    hap = HomematicipHAP(hass, hmip_config_entry)
    assert hap
    with patch(
        "homeassistant.components.homematicip_cloud.hap.AsyncHome",
        return_value=simple_mock_home,
    ), patch.object(hap, "async_connect", return_value=mock_coro(None)):
        assert await hap.async_setup()


async def test_hap_create_exception(hass, hmip_config_entry, simple_mock_home):
    """Mock AsyncHome to execute get_hap."""
    hass.config.components.add(HMIPC_DOMAIN)
    hap = HomematicipHAP(hass, hmip_config_entry)
    assert hap

    with patch.object(hap, "get_hap", side_effect=HmipConnectionError), pytest.raises(
        HmipConnectionError
    ):
        await hap.async_setup()

    simple_mock_home.init.side_effect = HmipConnectionError
    with patch(
        "homeassistant.components.homematicip_cloud.hap.AsyncHome",
        return_value=simple_mock_home,
    ), pytest.raises(ConfigEntryNotReady):
        await hap.async_setup()


async def test_auth_create(hass, simple_mock_auth):
    """Mock AsyncAuth to execute get_auth."""
    config = {
        const.HMIPC_HAPID: HAPID,
        const.HMIPC_PIN: HAPPIN,
        const.HMIPC_NAME: "hmip",
    }
    hmip_auth = HomematicipAuth(hass, config)
    assert hmip_auth

    with patch(
        "homeassistant.components.homematicip_cloud.hap.AsyncAuth",
        return_value=simple_mock_auth,
    ):
        assert await hmip_auth.async_setup()
        await hass.async_block_till_done()
        assert hmip_auth.auth.pin == HAPPIN


async def test_auth_create_exception(hass, simple_mock_auth):
    """Mock AsyncAuth to execute get_auth."""
    config = {
        const.HMIPC_HAPID: HAPID,
        const.HMIPC_PIN: HAPPIN,
        const.HMIPC_NAME: "hmip",
    }
    hmip_auth = HomematicipAuth(hass, config)
    simple_mock_auth.connectionRequest.side_effect = HmipConnectionError
    assert hmip_auth
    with patch(
        "homeassistant.components.homematicip_cloud.hap.AsyncAuth",
        return_value=simple_mock_auth,
    ):
        assert await hmip_auth.async_setup()
        await hass.async_block_till_done()
        assert not hmip_auth.auth

    with patch(
        "homeassistant.components.homematicip_cloud.hap.AsyncAuth",
        return_value=simple_mock_auth,
    ):
        assert not await hmip_auth.get_auth(hass, HAPID, HAPPIN)
