"""Unit tests for the CalDav integration."""

import threading
from unittest.mock import MagicMock, patch

from caldav.lib.error import AuthorizationError, DAVError
import pytest
import requests

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
async def mock_add_to_hass(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture to add the ConfigEntry."""
    config_entry.add_to_hass(hass)


async def test_load_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading of the config entry."""
    assert config_entry.state is ConfigEntryState.NOT_LOADED

    with patch("homeassistant.components.caldav.config_flow.caldav.DAVClient"):
        await hass.config_entries.async_setup(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_session_closes_on_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Underlying HTTP session is torn down off-loop when the entry unloads.

    Two guarantees in one test:

    1. Lifecycle: the session is closed exactly once, only at unload.
       Closing between requests races with concurrent searches because
       caldav 2.1.0+ multiplexes all requests over a single niquests
       ``Session`` (HTTP/2), so cleanup must happen after all platforms have
       torn down.
    2. Threading: ``session.close()`` is synchronous and can block on
       socket teardown, so the production code dispatches it via the
       executor. Capture the thread the close runs on and assert it is
       *not* the event-loop thread, to lock that in.
    """
    close_thread: threading.Thread | None = None
    event_loop_thread = threading.current_thread()

    def record_thread() -> None:
        nonlocal close_thread
        close_thread = threading.current_thread()

    session = MagicMock()
    session.close.side_effect = record_thread

    # Patch ``DAVClient`` on the third-party ``caldav`` package as it is
    # imported by ``homeassistant.components.caldav.__init__`` — that is the
    # module that constructs the client and registers the unload hook whose
    # ``session.close()`` we are verifying.
    with patch("homeassistant.components.caldav.caldav.DAVClient") as mock_client:
        mock_client.return_value.session = session
        await hass.config_entries.async_setup(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.LOADED
        session.close.assert_not_called()

        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    session.close.assert_called_once()
    assert close_thread is not None
    assert close_thread is not event_loop_thread, (
        "session.close() ran on the event-loop thread — the executor offload "
        "in async_setup_entry has regressed and a blocking close will stall HA"
    )


@pytest.mark.parametrize(
    ("side_effect", "expected_state", "expected_flows"),
    [
        (Exception(), ConfigEntryState.SETUP_ERROR, []),
        (requests.ConnectionError(), ConfigEntryState.SETUP_RETRY, []),
        (requests.Timeout(), ConfigEntryState.SETUP_RETRY, []),
        (DAVError(), ConfigEntryState.SETUP_RETRY, []),
        (
            AuthorizationError(reason="Unauthorized"),
            ConfigEntryState.SETUP_ERROR,
            ["reauth_confirm"],
        ),
        (AuthorizationError(reason="Other"), ConfigEntryState.SETUP_ERROR, []),
    ],
)
async def test_client_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
    expected_flows: list[str],
) -> None:
    """Test CalDAV client failures in setup."""

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    with patch(
        "homeassistant.components.caldav.config_flow.caldav.DAVClient"
    ) as mock_client:
        mock_client.return_value.principal.side_effect = side_effect
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is expected_state

    flows = hass.config_entries.flow.async_progress()
    assert [flow.get("step_id") for flow in flows] == expected_flows
