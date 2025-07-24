"""Test HomematicIP Cloud accesspoint."""

from unittest.mock import AsyncMock, MagicMock, Mock, patch

from homematicip.auth import Auth
from homematicip.connection.connection_context import ConnectionContext
from homematicip.exceptions.connection_exceptions import HmipConnectionError
import pytest

from homeassistant.components.homematicip_cloud import DOMAIN
from homeassistant.components.homematicip_cloud.const import (
    HMIPC_AUTHTOKEN,
    HMIPC_HAPID,
    HMIPC_NAME,
    HMIPC_PIN,
)
from homeassistant.components.homematicip_cloud.errors import HmipcConnectionError
from homeassistant.components.homematicip_cloud.hap import (
    AsyncHome,
    HomematicipAuth,
    HomematicipHAP,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .helper import HAPID, HAPPIN, HomeFactory

from tests.common import MockConfigEntry


async def test_auth_setup(hass: HomeAssistant) -> None:
    """Test auth setup for client registration."""
    config = {HMIPC_HAPID: "ABC123", HMIPC_PIN: "123", HMIPC_NAME: "hmip"}
    hmip_auth = HomematicipAuth(hass, config)
    with patch.object(hmip_auth, "get_auth"):
        assert await hmip_auth.async_setup()


async def test_auth_setup_connection_error(hass: HomeAssistant) -> None:
    """Test auth setup connection error behaviour."""
    config = {HMIPC_HAPID: "ABC123", HMIPC_PIN: "123", HMIPC_NAME: "hmip"}
    hmip_auth = HomematicipAuth(hass, config)
    with patch.object(hmip_auth, "get_auth", side_effect=HmipcConnectionError):
        assert not await hmip_auth.async_setup()


async def test_auth_auth_check_and_register(hass: HomeAssistant) -> None:
    """Test auth client registration."""
    config = {HMIPC_HAPID: "ABC123", HMIPC_PIN: "123", HMIPC_NAME: "hmip"}

    hmip_auth = HomematicipAuth(hass, config)
    hmip_auth.auth = Mock(spec=Auth)
    with (
        patch.object(hmip_auth.auth, "is_request_acknowledged", return_value=True),
        patch.object(hmip_auth.auth, "request_auth_token", return_value="ABC"),
        patch.object(
            hmip_auth.auth,
            "confirm_auth_token",
        ),
    ):
        assert await hmip_auth.async_checkbutton()
        assert await hmip_auth.async_register() == "ABC"


async def test_auth_auth_check_and_register_with_exception(hass: HomeAssistant) -> None:
    """Test auth client registration."""
    config = {HMIPC_HAPID: "ABC123", HMIPC_PIN: "123", HMIPC_NAME: "hmip"}
    hmip_auth = HomematicipAuth(hass, config)
    hmip_auth.auth = Mock(spec=Auth)
    with (
        patch.object(
            hmip_auth.auth, "is_request_acknowledged", side_effect=HmipConnectionError
        ),
        patch.object(
            hmip_auth.auth, "request_auth_token", side_effect=HmipConnectionError
        ),
    ):
        assert not await hmip_auth.async_checkbutton()
        assert await hmip_auth.async_register() is False


async def test_hap_setup_works(hass: HomeAssistant) -> None:
    """Test a successful setup of a accesspoint."""
    # This test should not be accessing the integration internals
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={HMIPC_HAPID: "ABC123", HMIPC_AUTHTOKEN: "123", HMIPC_NAME: "hmip"},
    )
    home = Mock()
    hap = HomematicipHAP(hass, entry)
    with patch.object(hap, "get_hap", return_value=home):
        async with entry.setup_lock:
            assert await hap.async_setup()

    assert hap.home is home


async def test_hap_setup_connection_error() -> None:
    """Test a failed accesspoint setup."""
    hass = Mock()
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={HMIPC_HAPID: "ABC123", HMIPC_AUTHTOKEN: "123", HMIPC_NAME: "hmip"},
    )
    hap = HomematicipHAP(hass, entry)
    with (
        patch.object(hap, "get_hap", side_effect=HmipcConnectionError),
        pytest.raises(ConfigEntryNotReady),
    ):
        async with entry.setup_lock:
            assert not await hap.async_setup()

    assert not hass.async_run_hass_job.mock_calls
    assert not hass.config_entries.flow.async_init.mock_calls


async def test_hap_reset_unloads_entry_if_setup(
    hass: HomeAssistant, default_mock_hap_factory: HomeFactory
) -> None:
    """Test calling reset while the entry has been setup."""
    mock_hap = await default_mock_hap_factory.async_get_mock_hap()
    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(config_entries) == 1
    assert config_entries[0].runtime_data == mock_hap
    # hap_reset is called during unload
    await hass.config_entries.async_unload(config_entries[0].entry_id)
    # entry is unloaded
    assert config_entries[0].state is ConfigEntryState.NOT_LOADED


async def test_hap_create(
    hass: HomeAssistant, hmip_config_entry: MockConfigEntry, simple_mock_home
) -> None:
    """Mock AsyncHome to execute get_hap."""
    hass.config.components.add(DOMAIN)
    hap = HomematicipHAP(hass, hmip_config_entry)
    assert hap
    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.ConnectionContextBuilder.build_context_async",
            return_value=ConnectionContext(),
        ),
        patch.object(hap, "async_connect"),
    ):
        async with hmip_config_entry.setup_lock:
            assert await hap.async_setup()


async def test_hap_create_exception(
    hass: HomeAssistant, hmip_config_entry: MockConfigEntry, mock_connection_init
) -> None:
    """Mock AsyncHome to execute get_hap."""
    hass.config.components.add(DOMAIN)

    hap = HomematicipHAP(hass, hmip_config_entry)
    assert hap

    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.ConnectionContextBuilder.build_context_async",
            return_value=ConnectionContext(),
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.AsyncHome.get_current_state_async",
            side_effect=Exception,
        ),
    ):
        assert not await hap.async_setup()

    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.ConnectionContextBuilder.build_context_async",
            return_value=ConnectionContext(),
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.AsyncHome.get_current_state_async",
            side_effect=HmipConnectionError,
        ),
        pytest.raises(ConfigEntryNotReady),
    ):
        await hap.async_setup()


async def test_auth_create(hass: HomeAssistant, simple_mock_auth) -> None:
    """Mock AsyncAuth to execute get_auth."""
    config = {HMIPC_HAPID: HAPID, HMIPC_PIN: HAPPIN, HMIPC_NAME: "hmip"}
    hmip_auth = HomematicipAuth(hass, config)
    assert hmip_auth

    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.Auth",
            return_value=simple_mock_auth,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.ConnectionContextBuilder.build_context_async",
            return_value=ConnectionContext(),
        ),
    ):
        assert await hmip_auth.async_setup()
        await hass.async_block_till_done()
        assert hmip_auth.auth.pin == HAPPIN


async def test_auth_create_exception(hass: HomeAssistant, simple_mock_auth) -> None:
    """Mock AsyncAuth to execute get_auth."""
    config = {HMIPC_HAPID: HAPID, HMIPC_PIN: HAPPIN, HMIPC_NAME: "hmip"}
    hmip_auth = HomematicipAuth(hass, config)
    simple_mock_auth.connection_request.side_effect = HmipConnectionError
    assert hmip_auth
    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.Auth",
            return_value=simple_mock_auth,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.ConnectionContextBuilder.build_context_async",
            return_value=ConnectionContext(),
        ),
    ):
        assert not await hmip_auth.async_setup()

    with (
        patch(
            "homeassistant.components.homematicip_cloud.hap.Auth",
            return_value=simple_mock_auth,
        ),
        patch(
            "homeassistant.components.homematicip_cloud.hap.ConnectionContextBuilder.build_context_async",
            return_value=ConnectionContext(),
        ),
    ):
        assert not await hmip_auth.get_auth(hass, HAPID, HAPPIN)


async def test_get_state_after_disconnect(
    hass: HomeAssistant, hmip_config_entry: MockConfigEntry, simple_mock_home
) -> None:
    """Test get state after disconnect."""
    hass.config.components.add(DOMAIN)
    hap = HomematicipHAP(hass, hmip_config_entry)
    assert hap

    simple_mock_home = AsyncMock(spec=AsyncHome, autospec=True)
    hap.home = simple_mock_home
    hap.home.websocket_is_connected = Mock(side_effect=[False, True])

    with (
        patch("asyncio.sleep", new=AsyncMock()) as mock_sleep,
        patch.object(hap, "get_state") as mock_get_state,
    ):
        assert not hap._ws_connection_closed.is_set()

        await hap.ws_connected_handler()
        mock_get_state.assert_not_called()

        await hap.ws_disconnected_handler()
        assert hap._ws_connection_closed.is_set()
        with patch(
            "homeassistant.components.homematicip_cloud.hap.AsyncHome.websocket_is_connected",
            return_value=True,
        ):
            await hap.ws_connected_handler()
            mock_get_state.assert_called_once()

    assert not hap._ws_connection_closed.is_set()
    hap.home.websocket_is_connected.assert_called()
    mock_sleep.assert_awaited_with(2)


async def test_try_get_state_exponential_backoff() -> None:
    """Test _try_get_state waits for websocket connection."""

    # Arrange: Create instance and mock home
    hap = HomematicipHAP(MagicMock(), MagicMock())
    hap.home = MagicMock()
    hap.home.websocket_is_connected = Mock(return_value=True)

    hap.get_state = AsyncMock(
        side_effect=[HmipConnectionError, HmipConnectionError, True]
    )

    with patch("asyncio.sleep", new=AsyncMock()) as mock_sleep:
        await hap._try_get_state()

    assert mock_sleep.mock_calls[0].args[0] == 8
    assert mock_sleep.mock_calls[1].args[0] == 16
    assert hap.get_state.call_count == 3


async def test_try_get_state_handle_exception() -> None:
    """Test _try_get_state handles exceptions."""
    # Arrange: Create instance and mock home
    hap = HomematicipHAP(MagicMock(), MagicMock())
    hap.home = MagicMock()

    expected_exception = Exception("Connection error")
    future = AsyncMock()
    future.result = Mock(side_effect=expected_exception)

    with patch("homeassistant.components.homematicip_cloud.hap._LOGGER") as mock_logger:
        hap.get_state_finished(future)

    mock_logger.error.assert_called_once_with(
        "Error updating state after HMIP access point reconnect: %s", expected_exception
    )


async def test_async_connect(
    hass: HomeAssistant, hmip_config_entry: MockConfigEntry, simple_mock_home
) -> None:
    """Test async_connect."""
    hass.config.components.add(DOMAIN)
    hap = HomematicipHAP(hass, hmip_config_entry)
    assert hap

    simple_mock_home = AsyncMock(spec=AsyncHome, autospec=True)

    await hap.async_connect(simple_mock_home)

    simple_mock_home.set_on_connected_handler.assert_called_once()
    simple_mock_home.set_on_disconnected_handler.assert_called_once()
    simple_mock_home.set_on_reconnect_handler.assert_called_once()
    simple_mock_home.enable_events.assert_called_once()
