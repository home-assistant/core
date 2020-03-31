"""Test HomematicIP Cloud accesspoint."""

from asynctest import Mock, patch
from homematicip.aio.auth import AsyncAuth
from homematicip.base.base_connection import HmipConnectionError
import pytest

from homeassistant.components.homematicip_cloud import DOMAIN as HMIPC_DOMAIN
from homeassistant.components.homematicip_cloud.const import (
    HMIPC_AUTHTOKEN,
    HMIPC_HAPID,
    HMIPC_NAME,
    HMIPC_PIN,
)
from homeassistant.components.homematicip_cloud.errors import HmipcConnectionError
from homeassistant.components.homematicip_cloud.hap import (
    HomematicipAuth,
    HomematicipHAP,
)
from homeassistant.config_entries import ENTRY_STATE_NOT_LOADED
from homeassistant.exceptions import ConfigEntryNotReady

from .helper import HAPID, HAPPIN


async def test_auth_setup(hass):
    """Test auth setup for client registration."""
    config = {HMIPC_HAPID: "ABC123", HMIPC_PIN: "123", HMIPC_NAME: "hmip"}
    hmip_auth = HomematicipAuth(hass, config)
    with patch.object(hmip_auth, "get_auth"):
        assert await hmip_auth.async_setup()


async def test_auth_setup_connection_error(hass):
    """Test auth setup connection error behaviour."""
    config = {HMIPC_HAPID: "ABC123", HMIPC_PIN: "123", HMIPC_NAME: "hmip"}
    hmip_auth = HomematicipAuth(hass, config)
    with patch.object(hmip_auth, "get_auth", side_effect=HmipcConnectionError):
        assert not await hmip_auth.async_setup()


async def test_auth_auth_check_and_register(hass):
    """Test auth client registration."""
    config = {HMIPC_HAPID: "ABC123", HMIPC_PIN: "123", HMIPC_NAME: "hmip"}

    hmip_auth = HomematicipAuth(hass, config)
    hmip_auth.auth = Mock(spec=AsyncAuth)
    with patch.object(
        hmip_auth.auth, "isRequestAcknowledged", return_value=True
    ), patch.object(
        hmip_auth.auth, "requestAuthToken", return_value="ABC"
    ), patch.object(
        hmip_auth.auth, "confirmAuthToken"
    ):
        assert await hmip_auth.async_checkbutton()
        assert await hmip_auth.async_register() == "ABC"


async def test_auth_auth_check_and_register_with_exception(hass):
    """Test auth client registration."""
    config = {HMIPC_HAPID: "ABC123", HMIPC_PIN: "123", HMIPC_NAME: "hmip"}
    hmip_auth = HomematicipAuth(hass, config)
    hmip_auth.auth = Mock(spec=AsyncAuth)
    with patch.object(
        hmip_auth.auth, "isRequestAcknowledged", side_effect=HmipConnectionError
    ), patch.object(
        hmip_auth.auth, "requestAuthToken", side_effect=HmipConnectionError
    ):
        assert not await hmip_auth.async_checkbutton()
        assert await hmip_auth.async_register() is False


async def test_hap_setup_works():
    """Test a successful setup of a accesspoint."""
    hass = Mock()
    entry = Mock()
    home = Mock()
    entry.data = {HMIPC_HAPID: "ABC123", HMIPC_AUTHTOKEN: "123", HMIPC_NAME: "hmip"}
    hap = HomematicipHAP(hass, entry)
    with patch.object(hap, "get_hap", return_value=home):
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
    entry.data = {HMIPC_HAPID: "ABC123", HMIPC_AUTHTOKEN: "123", HMIPC_NAME: "hmip"}
    hap = HomematicipHAP(hass, entry)
    with patch.object(hap, "get_hap", side_effect=HmipcConnectionError), pytest.raises(
        ConfigEntryNotReady
    ):
        assert not await hap.async_setup()

    assert not hass.async_add_job.mock_calls
    assert not hass.config_entries.flow.async_init.mock_calls


async def test_hap_reset_unloads_entry_if_setup(hass, default_mock_hap_factory):
    """Test calling reset while the entry has been setup."""
    mock_hap = await default_mock_hap_factory.async_get_mock_hap()
    assert hass.data[HMIPC_DOMAIN][HAPID] == mock_hap
    config_entries = hass.config_entries.async_entries(HMIPC_DOMAIN)
    assert len(config_entries) == 1
    # hap_reset is called during unload
    await hass.config_entries.async_unload(config_entries[0].entry_id)
    # entry is unloaded
    assert config_entries[0].state == ENTRY_STATE_NOT_LOADED
    assert hass.data[HMIPC_DOMAIN] == {}


async def test_hap_create(hass, hmip_config_entry, simple_mock_home):
    """Mock AsyncHome to execute get_hap."""
    hass.config.components.add(HMIPC_DOMAIN)
    hap = HomematicipHAP(hass, hmip_config_entry)
    assert hap
    with patch.object(hap, "async_connect"):
        assert await hap.async_setup()


async def test_hap_create_exception(hass, hmip_config_entry, mock_connection_init):
    """Mock AsyncHome to execute get_hap."""
    hass.config.components.add(HMIPC_DOMAIN)

    hap = HomematicipHAP(hass, hmip_config_entry)
    assert hap

    with patch(
        "homeassistant.components.homematicip_cloud.hap.AsyncHome.get_current_state",
        side_effect=Exception,
    ):
        assert not await hap.async_setup()

    with patch(
        "homeassistant.components.homematicip_cloud.hap.AsyncHome.get_current_state",
        side_effect=HmipConnectionError,
    ), pytest.raises(ConfigEntryNotReady):
        await hap.async_setup()


async def test_auth_create(hass, simple_mock_auth):
    """Mock AsyncAuth to execute get_auth."""
    config = {HMIPC_HAPID: HAPID, HMIPC_PIN: HAPPIN, HMIPC_NAME: "hmip"}
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
    config = {HMIPC_HAPID: HAPID, HMIPC_PIN: HAPPIN, HMIPC_NAME: "hmip"}
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
