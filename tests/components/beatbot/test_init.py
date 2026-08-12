"""Tests for Beatbot config entry setup and unload."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from beatbot_cloud import BeatbotAuthenticationError, BeatbotDeviceData
import pytest

from homeassistant.components.beatbot import config_entry_oauth2_flow
from homeassistant.components.beatbot.const import DOMAIN, PLATFORMS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    OAuth2TokenRequestReauthError,
)
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_oauth_implementation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the config entry's OAuth implementation available."""
    monkeypatch.setattr(
        config_entry_oauth2_flow,
        "async_get_config_entry_implementation",
        AsyncMock(return_value=Mock()),
    )


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
            "homeassistant.components.beatbot.BeatbotClient", return_value=Mock()
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
        entry, PLATFORMS
    )
    event_client_cls.assert_called_once()
    event_client.async_start.assert_called_once()
    assert entry.runtime_data.coordinator is coordinator
    assert entry.runtime_data.event_client is event_client


async def test_async_setup_entry_loads_sensor_platform(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Load pool cleaners through the config entry sensor platform."""
    entry = _entry()
    entry.add_to_hass(hass)
    device = BeatbotDeviceData(
        device_id="pool-cleaner-1",
        product_id="new-product-id",
        product_category="pool_clean_bot",
        work_status=0,
        work_mode=0,
        error_code=0,
        battery_level=80,
        versions=[],
        is_online=True,
    )
    api = SimpleNamespace(
        get_devices=AsyncMock(return_value=[device]),
        get_device_states=AsyncMock(return_value={}),
    )
    event_client = Mock()
    event_client.async_start = Mock()
    event_client.async_stop = AsyncMock()

    with (
        patch("homeassistant.components.beatbot.BeatbotClient", return_value=api),
        patch(
            "homeassistant.components.beatbot.BeatbotEventClient",
            return_value=event_client,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    status_entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "pool-cleaner-1_status"
    )
    battery_entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "pool-cleaner-1_battery"
    )
    error_entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, "pool-cleaner-1_error"
    )
    assert status_entity_id is not None
    assert battery_entity_id is not None
    assert error_entity_id is not None
    assert hass.states.get(status_entity_id) is not None
    assert hass.states.get(battery_entity_id) is not None
    assert hass.states.get(error_entity_id) is not None


@pytest.mark.parametrize(
    "refresh_error",
    [
        ConfigEntryAuthFailed(),
        OAuth2TokenRequestReauthError(
            request_info=SimpleNamespace(real_url="https://oauth.beatbot.com/token"),
            status=400,
            domain=DOMAIN,
        ),
    ],
)
async def test_access_token_provider_translates_oauth_refresh_rejection(
    hass: HomeAssistant, refresh_error: Exception
) -> None:
    """Translate terminal OAuth refresh errors for the client library."""
    entry = _entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    session = SimpleNamespace(
        token={"access_token": "access-token"},
        async_ensure_token_valid=AsyncMock(
            side_effect=[
                None,
                refresh_error,
            ]
        ),
    )
    access_token_provider = None

    def _client(_region: str, _session, access_token):
        nonlocal access_token_provider
        access_token_provider = access_token
        return Mock()

    async def _first_refresh() -> None:
        assert access_token_provider is not None
        assert await access_token_provider() == "access-token"
        with pytest.raises(BeatbotAuthenticationError):
            await access_token_provider()

    coordinator = Mock()
    coordinator.async_config_entry_first_refresh = AsyncMock(side_effect=_first_refresh)
    event_client = Mock()

    with (
        patch(
            "homeassistant.components.beatbot.config_entry_oauth2_flow.OAuth2Session",
            return_value=session,
        ),
        patch("homeassistant.components.beatbot.BeatbotClient", side_effect=_client),
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

    assert session.async_ensure_token_valid.await_count == 2


async def test_async_unload_entry_stops_events_and_unloads_platforms(
    hass: HomeAssistant,
) -> None:
    """Unload stops the event stream after unloading platforms."""
    entry = _entry()
    entry.add_to_hass(hass)
    hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    coordinator = Mock()
    coordinator.async_config_entry_first_refresh = AsyncMock()
    event_client = Mock()
    event_client.async_start = Mock()
    event_client.async_stop = AsyncMock()

    with (
        patch("homeassistant.components.beatbot.BeatbotClient", return_value=Mock()),
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
    hass.config_entries.async_unload_platforms.assert_awaited_once_with(
        entry, PLATFORMS
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
    event_client = Mock()
    event_client.async_start = Mock()
    event_client.async_stop = AsyncMock()

    with (
        patch("homeassistant.components.beatbot.BeatbotClient", return_value=Mock()),
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
        patch("homeassistant.components.beatbot.BeatbotClient", return_value=Mock()),
        patch(
            "homeassistant.components.beatbot.BeatbotCoordinator",
            return_value=coordinator,
        ),
        patch(
            "homeassistant.components.beatbot.BeatbotEventClient"
        ) as event_client_cls,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is expected_state
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    hass.config_entries.async_forward_entry_setups.assert_not_called()
    event_client_cls.assert_not_called()


async def test_async_setup_entry_not_ready(hass: HomeAssistant) -> None:
    """A transient first refresh failure schedules setup retry."""
    await _assert_first_refresh_failure(
        hass, ConfigEntryNotReady, ConfigEntryState.SETUP_RETRY
    )


async def test_async_setup_entry_auth_failed(hass: HomeAssistant) -> None:
    """An authentication failure fails config entry setup."""
    await _assert_first_refresh_failure(
        hass, ConfigEntryAuthFailed, ConfigEntryState.SETUP_ERROR
    )
