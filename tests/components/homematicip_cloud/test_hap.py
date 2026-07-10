"""Test HomematicIP Cloud accesspoint."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from homematicip.auth import Auth
from homematicip.connection.connection_context import ConnectionContext
from homematicip.exceptions.connection_exceptions import (
    HmipAuthenticationError,
    HmipConnectionError,
)
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
    """ws_connected after a disconnect triggers a state refresh via the library."""
    hass.config.components.add(DOMAIN)
    hap = HomematicipHAP(hass, hmip_config_entry)
    assert hap

    simple_mock_home = AsyncMock(spec=AsyncHome, autospec=True)
    simple_mock_home.devices = []
    hap.home = simple_mock_home

    assert not hap._ws_connection_closed.is_set()

    await hap.ws_connected_handler()
    simple_mock_home.refresh_state_after_reconnect_async.assert_not_called()

    await hap.ws_disconnected_handler()
    assert hap._ws_connection_closed.is_set()

    await hap.ws_connected_handler()
    await hass.async_block_till_done()
    simple_mock_home.refresh_state_after_reconnect_async.assert_called_once()
    assert not hap._ws_connection_closed.is_set()


async def test_get_state_after_ap_reconnect(
    hass: HomeAssistant, hmip_config_entry: MockConfigEntry, simple_mock_home
) -> None:
    """Test state recovery after access point reconnects to cloud.

    When the access point loses its cloud connection, async_update sets all
    devices to unavailable. When the access point reconnects (home.connected
    becomes True), async_update should trigger a state refresh to restore
    entity availability.
    """
    hass.config.components.add(DOMAIN)
    hap = HomematicipHAP(hass, hmip_config_entry)
    assert hap

    simple_mock_home = MagicMock(spec=AsyncHome)
    simple_mock_home.devices = []
    simple_mock_home.refresh_state_after_reconnect_async = AsyncMock()
    hap.home = simple_mock_home

    # Initially not disconnected
    assert not hap._ws_connection_closed.is_set()

    # Access point loses cloud connection
    hap.home.connected = False
    hap.async_update()
    assert hap._ws_connection_closed.is_set()
    simple_mock_home.refresh_state_after_reconnect_async.assert_not_called()

    # Access point reconnects to cloud
    hap.home.connected = True
    hap.async_update()

    # Let _try_get_state run
    await hass.async_block_till_done()
    simple_mock_home.refresh_state_after_reconnect_async.assert_called_once()
    assert not hap._ws_connection_closed.is_set()


async def test_try_get_state_delegates_to_library_then_post_processes() -> None:
    """_try_get_state calls refresh_state_after_reconnect_async then runs post-processing."""
    hap = HomematicipHAP(MagicMock(), MagicMock())
    hap.home = MagicMock()
    hap.home.refresh_state_after_reconnect_async = AsyncMock()
    device_changed = MagicMock(unreach=False)
    device_unchanged = MagicMock(unreach=True)
    hap.home.devices = [device_changed, device_unchanged]

    await hap._try_get_state()

    hap.home.refresh_state_after_reconnect_async.assert_awaited_once()
    assert device_changed.unreach is False
    assert device_unchanged.unreach is False


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


async def test_try_get_state_auth_error_triggers_reauth(
    hass: HomeAssistant, hmip_config_entry: MockConfigEntry, simple_mock_home
) -> None:
    """An auth error from the library triggers a reauth flow without post-processing."""
    hass.config.components.add(DOMAIN)
    hmip_config_entry.add_to_hass(hass)
    hap = HomematicipHAP(hass, hmip_config_entry)
    assert hap

    hap.home = MagicMock(spec=AsyncHome)
    hap.home.devices = [MagicMock(unreach=True)]
    hap.home.refresh_state_after_reconnect_async = AsyncMock(
        side_effect=HmipAuthenticationError
    )

    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    await hap._try_get_state()
    await hass.async_block_till_done()

    # Auth error path: post-processing must NOT have run.
    assert hap.home.devices[0].unreach is True
    # Should have triggered a reauth flow
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == "reauth"


def _set_diagnostic_defaults(home: MagicMock) -> None:
    """Configure quiet defaults for diagnostic methods on a mocked AsyncHome."""
    home.websocket_last_disconnect_reason = Mock(return_value=None)
    home.websocket_reconnect_attempt_count = Mock(return_value=None)
    home.websocket_seconds_since_last_message = Mock(return_value=None)
    home.websocket_message_count = Mock(return_value=None)


async def test_start_get_state_task_cancels_existing_task(
    hass: HomeAssistant, hmip_config_entry: MockConfigEntry
) -> None:
    """Starting a reconnect refresh cancels any in-flight refresh."""
    hass.config.components.add(DOMAIN)
    hap = HomematicipHAP(hass, hmip_config_entry)
    hap.home = MagicMock(spec=AsyncHome)

    old_task = MagicMock()
    old_task.done.return_value = False
    hap._get_state_task = old_task

    with patch.object(hap, "_try_get_state", new=AsyncMock()):
        hap._start_get_state_task()

    old_task.cancel.assert_called_once()
    assert hap._get_state_task is not old_task
    assert not hap._ws_connection_closed.is_set()


async def test_start_get_state_task_skips_cancel_for_completed_task(
    hass: HomeAssistant, hmip_config_entry: MockConfigEntry
) -> None:
    """Starting a reconnect refresh does not cancel a completed task."""
    hass.config.components.add(DOMAIN)
    hap = HomematicipHAP(hass, hmip_config_entry)
    hap.home = MagicMock(spec=AsyncHome)

    old_task = MagicMock()
    old_task.done.return_value = True
    hap._get_state_task = old_task

    with patch.object(hap, "_try_get_state", new=AsyncMock()):
        hap._start_get_state_task()

    old_task.cancel.assert_not_called()


async def test_replaced_get_state_task_cancellation_is_not_logged_as_error(
    hass: HomeAssistant, hmip_config_entry: MockConfigEntry
) -> None:
    """Replacing an in-flight refresh must not log the cancelled task as error."""
    hass.config.components.add(DOMAIN)
    hap = HomematicipHAP(hass, hmip_config_entry)
    hap.home = MagicMock(spec=AsyncHome)
    hap.home.devices = []
    _set_diagnostic_defaults(hap.home)

    continue_refresh = asyncio.Event()

    async def block_refresh() -> None:
        await continue_refresh.wait()

    hap.home.refresh_state_after_reconnect_async = AsyncMock(side_effect=block_refresh)

    with patch("homeassistant.components.homematicip_cloud.hap._LOGGER") as logger:
        hap._ws_connection_closed.set()
        hap._start_get_state_task()
        first_task = hap._get_state_task
        assert first_task is not None
        await asyncio.sleep(0)

        hap._ws_connection_closed.set()
        hap._start_get_state_task()
        second_task = hap._get_state_task
        assert second_task is not None
        assert second_task is not first_task
        await asyncio.sleep(0)

        continue_refresh.set()
        await hass.async_block_till_done()

    assert first_task.cancelled()
    logger.error.assert_not_called()


async def test_websocket_diagnostic_context_omits_none_values() -> None:
    """None-valued diagnostics are omitted from the context string."""
    hap = HomematicipHAP(MagicMock(), MagicMock())
    hap.home = MagicMock()
    hap.home.websocket_last_disconnect_reason = Mock(return_value=None)
    hap.home.websocket_reconnect_attempt_count = Mock(return_value=2)
    hap.home.websocket_seconds_since_last_message = Mock(return_value=None)
    hap.home.websocket_message_count = Mock(return_value=10)

    context = hap._websocket_diagnostic_context()

    assert "last_disconnect_reason" not in context
    assert "reconnect_attempts=2" in context
    assert "message_count=10" in context


async def test_websocket_diagnostic_context_falls_back_when_all_unknown() -> None:
    """Helper returns a non-empty fallback if every diagnostic is None."""
    hap = HomematicipHAP(MagicMock(), MagicMock())
    hap.home = MagicMock()
    _set_diagnostic_defaults(hap.home)

    assert hap._websocket_diagnostic_context() == "no diagnostics available"


async def test_on_websocket_stale_logs_warning_then_error() -> None:
    """Library callback maps severity to log level (warning vs error)."""
    hap = HomematicipHAP(MagicMock(), MagicMock())
    hap.home = MagicMock()
    _set_diagnostic_defaults(hap.home)

    with patch("homeassistant.components.homematicip_cloud.hap._LOGGER") as logger:
        await hap._on_websocket_stale("warning", 400)
    logger.warning.assert_called_once()
    logger.error.assert_not_called()

    with patch("homeassistant.components.homematicip_cloud.hap._LOGGER") as logger:
        await hap._on_websocket_stale("error", 1900)
    logger.error.assert_called_once()
    logger.warning.assert_not_called()


async def test_async_connect_registers_stale_handler() -> None:
    """async_connect registers the library websocket-stale callback."""
    hap = HomematicipHAP(MagicMock(), MagicMock())
    home = MagicMock()
    home.enable_events = AsyncMock()
    home.set_on_websocket_stale_handler = MagicMock()

    await hap.async_connect(home)

    home.set_on_websocket_stale_handler.assert_called_once_with(hap._on_websocket_stale)


async def test_on_websocket_stale_log_format(caplog: pytest.LogCaptureFixture) -> None:
    """Warning has the rounded seconds; diagnostic context is at debug level."""
    hap = HomematicipHAP(MagicMock(), MagicMock())
    hap.home = MagicMock()
    _set_diagnostic_defaults(hap.home)
    hap.home.websocket_message_count = Mock(return_value=42)

    with caplog.at_level("DEBUG"):
        await hap._on_websocket_stale("warning", 423.7)

    assert "424" in caplog.text  # %.0f rounds
    assert "message_count=42" in caplog.text

    warning_records = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any("424" in r.getMessage() for r in warning_records)
    assert not any("message_count" in r.getMessage() for r in warning_records)


async def test_get_state_clears_unreach_on_unchanged_devices() -> None:
    """get_state must clear stale unreach flags after a reconnect.

    set_all_to_unavailable() sets unreach=True on all devices on disconnect;
    get_current_state_async() only updates devices whose state actually
    changed, so unchanged devices stay marked unreachable. We must clear it.
    """
    hap = HomematicipHAP(MagicMock(), MagicMock())
    hap.home = MagicMock()
    hap.home.get_current_state_async = AsyncMock()
    device_changed = MagicMock(unreach=False)
    device_unchanged = MagicMock(unreach=True)
    hap.home.devices = [device_changed, device_unchanged]

    await hap.get_state()

    assert device_changed.unreach is False
    assert device_unchanged.unreach is False
