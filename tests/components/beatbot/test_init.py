"""Tests for Beatbot config entry setup and unload."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.beatbot.iot.const import DOMAIN, SUPPORTED_PLATFORMS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from tests.common import MockConfigEntry


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id="account-1",
        title="Beatbot",
        data={
            "auth_implementation": DOMAIN,
            "region": "cn",
            "token": {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "token_type": "bearer",
            },
        },
    )


async def test_async_setup_entry_starts_runtime_objects(
    hass: HomeAssistant,
) -> None:
    """Successful setup creates runtime data, loads platforms, and starts events."""
    entry = _entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    coordinator = Mock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    event_client = Mock()
    event_client.async_start = Mock()

    with (
        patch(
            "homeassistant.components.beatbot.BeatbotAPI", return_value=Mock()
        ) as api_cls,
        patch(
            "homeassistant.components.beatbot.BeatbotCoordinator",
            return_value=coordinator,
        ) as coordinator_cls,
        patch(
            "homeassistant.components.beatbot.BeatbotEventClient",
            return_value=event_client,
        ) as event_client_cls,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    api_cls.assert_called_once()
    coordinator_cls.assert_called_once()
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(
        entry, SUPPORTED_PLATFORMS
    )
    event_client_cls.assert_called_once()
    event_client.async_start.assert_called_once()
    assert entry.runtime_data.coordinator is coordinator
    assert entry.runtime_data.event_client is event_client


async def test_async_unload_entry_stops_events_and_unloads_platforms(
    hass: HomeAssistant,
) -> None:
    """Unload stops the event stream and cancels pending refresh tasks."""
    entry = _entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    coordinator = Mock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_cancel_pending_refreshes = Mock()
    event_client = Mock()
    event_client.async_start = Mock()
    event_client.async_stop = AsyncMock()

    with (
        patch("homeassistant.components.beatbot.BeatbotAPI", return_value=Mock()),
        patch(
            "homeassistant.components.beatbot.BeatbotCoordinator",
            return_value=coordinator,
        ),
        patch(
            "homeassistant.components.beatbot.BeatbotEventClient",
            return_value=event_client,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert await hass.config_entries.async_unload(entry.entry_id)

    event_client.async_stop.assert_awaited_once()
    coordinator.async_cancel_pending_refreshes.assert_called_once()
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(
        entry, SUPPORTED_PLATFORMS
    )


async def test_async_unload_failure_keeps_runtime_services(
    hass: HomeAssistant,
) -> None:
    """Keep runtime services active when platform unload fails."""
    entry = _entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=False)
    coordinator = Mock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    coordinator.async_cancel_pending_refreshes = Mock()
    event_client = Mock()
    event_client.async_start = Mock()
    event_client.async_stop = AsyncMock()

    with (
        patch("homeassistant.components.beatbot.BeatbotAPI", return_value=Mock()),
        patch(
            "homeassistant.components.beatbot.BeatbotCoordinator",
            return_value=coordinator,
        ),
        patch(
            "homeassistant.components.beatbot.BeatbotEventClient",
            return_value=event_client,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert not await hass.config_entries.async_unload(entry.entry_id)

    event_client.async_stop.assert_not_awaited()
    coordinator.async_cancel_pending_refreshes.assert_not_called()


async def _assert_first_refresh_failure(
    hass: HomeAssistant,
    error: type[Exception],
    expected_state: ConfigEntryState,
) -> None:
    entry = _entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    coordinator = Mock()
    coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=error)

    with (
        patch("homeassistant.components.beatbot.BeatbotAPI", return_value=Mock()),
        patch(
            "homeassistant.components.beatbot.BeatbotCoordinator",
            return_value=coordinator,
        ),
        patch(
            "homeassistant.components.beatbot.BeatbotEventClient"
        ) as event_client_cls,
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is expected_state
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_not_called()
    event_client_cls.assert_not_called()


async def test_async_setup_entry_not_ready(hass: HomeAssistant) -> None:
    """A transient first refresh failure schedules setup retry."""
    await _assert_first_refresh_failure(
        hass, ConfigEntryNotReady, ConfigEntryState.SETUP_RETRY
    )


@pytest.mark.parametrize(
    "ignore_missing_translations",
    [
        [
            "component.homeassistant.issues.config_entry_reauth.title",
            "component.homeassistant.issues.config_entry_reauth.description",
        ]
    ],
)
async def test_async_setup_entry_auth_failed(hass: HomeAssistant) -> None:
    """An authentication failure starts reauthentication."""
    await _assert_first_refresh_failure(
        hass, ConfigEntryAuthFailed, ConfigEntryState.SETUP_ERROR
    )
