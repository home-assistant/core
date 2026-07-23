"""Tests for Beatbot config entry setup and unload."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.beatbot import async_setup_entry, async_unload_entry
from homeassistant.components.beatbot.iot.const import DOMAIN, SUPPORTED_PLATFORMS
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
        # Exercise construction order directly; config entry orchestration is mocked.
        # pylint: disable-next=home-assistant-tests-direct-async-setup-entry
        assert await async_setup_entry(hass, entry) is True

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
        # pylint: disable-next=home-assistant-tests-direct-async-setup-entry
        await async_setup_entry(hass, entry)
        assert await async_unload_entry(hass, entry) is True

    event_client.async_stop.assert_awaited_once()
    coordinator.async_cancel_pending_refreshes.assert_called_once()
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(
        entry, SUPPORTED_PLATFORMS
    )


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ConfigEntryNotReady, ConfigEntryNotReady),
        (ConfigEntryAuthFailed, ConfigEntryAuthFailed),
    ],
)
async def test_async_setup_entry_propagates_first_refresh_failures(
    hass: HomeAssistant,
    error: type[Exception],
    expected: type[Exception],
) -> None:
    """Setup fails before platform/event setup when the first refresh fails."""
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
        pytest.raises(expected),
    ):
        # pylint: disable-next=home-assistant-tests-direct-async-setup-entry
        await async_setup_entry(hass, entry)

    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_not_called()
    event_client_cls.assert_not_called()
