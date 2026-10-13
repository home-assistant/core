"""Test loading of the Tibber config entry."""

import asyncio
from collections.abc import Awaitable, Callable
import time
from unittest.mock import ANY, MagicMock, patch

import pytest

from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber import DOMAIN
from homeassistant.components.tibber.const import AUTH_IMPLEMENTATION
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_entry_unload(
    recorder_mock: Recorder, hass: HomeAssistant, mock_tibber_setup: MagicMock
) -> None:
    """Test unloading the entry."""
    entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, "tibber")
    assert entry.state is ConfigEntryState.LOADED

    mock_tibber_setup.set_access_token.reset_mock()
    await hass.config_entries.async_unload(entry.entry_id)
    mock_tibber_setup.rt_disconnect.assert_called_once()
    mock_tibber_setup.set_access_token.assert_not_called()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def _hang_forever() -> None:
    """Simulate a realtime disconnect that never completes."""
    await asyncio.Event().wait()


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(_hang_forever, id="timeout"),
        pytest.param(Exception("Disconnect failed"), id="exception"),
    ],
)
async def test_entry_unload_rt_disconnect_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_tibber_setup: MagicMock,
    side_effect: Exception | Callable[[], Awaitable[None]],
) -> None:
    """Test the entry unloads even if disconnecting the client fails."""
    entry = hass.config_entries.async_entry_for_domain_unique_id(DOMAIN, "tibber")
    assert entry.state is ConfigEntryState.LOADED

    mock_tibber_setup.rt_disconnect.side_effect = side_effect
    with patch("homeassistant.components.tibber.DISCONNECT_TIMEOUT", 0.05):
        await hass.config_entries.async_unload(entry.entry_id)
    mock_tibber_setup.rt_disconnect.assert_called_once()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert entry.state is ConfigEntryState.NOT_LOADED


async def _async_trigger_client_fetch(hass: HomeAssistant) -> None:
    """Make the integration fetch its client through a public entity action."""
    await hass.services.async_call(
        "notify",
        "send_message",
        {"entity_id": "notify.tibber", "message": "message"},
        blocking=True,
    )


@pytest.mark.usefixtures("recorder_mock", "mock_tibber_setup")
async def test_client_created_once_and_reused(
    hass: HomeAssistant,
    tibber_client_cls: MagicMock,
    tibber_mock: MagicMock,
) -> None:
    """Ensure setup builds one authenticated client that later fetches reuse."""
    tibber_client_cls.assert_called_once_with(
        access_token="test-token",
        websession=ANY,
        time_zone=ANY,
        ssl=ANY,
        refresh_access_token=ANY,
    )

    # The library refreshes its own realtime token through this callback.
    refresh_access_token = tibber_client_cls.call_args.kwargs["refresh_access_token"]
    assert await refresh_access_token() == "test-token"

    tibber_mock.set_access_token.reset_mock()
    await _async_trigger_client_fetch(hass)

    tibber_client_cls.assert_called_once()
    tibber_mock.set_access_token.assert_awaited_once_with("test-token")


@pytest.mark.usefixtures("recorder_mock", "mock_tibber_setup")
async def test_rotated_token_pushed_to_cached_client(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tibber_client_cls: MagicMock,
    tibber_mock: MagicMock,
) -> None:
    """Ensure a rotated OAuth token reaches the cached client on the next fetch."""
    hass.config_entries.async_update_entry(
        config_entry,
        data={
            **config_entry.data,
            "token": {**config_entry.data["token"], CONF_ACCESS_TOKEN: "token-2"},
        },
    )

    tibber_mock.set_access_token.reset_mock()
    await _async_trigger_client_fetch(hass)

    tibber_client_cls.assert_called_once()
    tibber_mock.set_access_token.assert_awaited_once_with("token-2")


@pytest.mark.usefixtures("recorder_mock", "tibber_mock", "setup_credentials")
async def test_setup_missing_access_token_triggers_reauth(
    hass: HomeAssistant,
) -> None:
    """Ensure an OAuth token without an access token triggers reauthentication."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            AUTH_IMPLEMENTATION: DOMAIN,
            "token": {
                "refresh_token": "refresh-token",
                "token_type": "Bearer",
                "expires_at": time.time() + 3600,
            },
        },
        unique_id="tibber",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


async def test_setup_requires_data_api_reauth(hass: HomeAssistant) -> None:
    """Ensure legacy entries trigger reauth to configure Data API."""
    hass.config.components.add("recorder")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ACCESS_TOKEN: "legacy-token"},
        unique_id="legacy",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_ERROR
