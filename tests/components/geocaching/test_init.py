"""Tests for the Geocaching integration."""

from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, patch

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.geocaching import async_update_entry
from homeassistant.components.geocaching.const import (
    DOMAIN,
    SUBENTRY_TYPE_TRACKED_CACHE,
)
from homeassistant.config_entries import ConfigEntryState, ConfigSubentry
from homeassistant.const import CONF_CODE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
)


async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.geocaching.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_update_listener(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the config entry update listener reloads for subentry changes."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    mock_config_entry.runtime_data = MagicMock()
    mock_config_entry.runtime_data.subentry_ids = frozenset()
    mock_config_entry.add_update_listener(async_update_entry)

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as async_schedule_reload:
        subentry = ConfigSubentry(
            data=MappingProxyType({CONF_CODE: "GC12345"}),
            subentry_type=SUBENTRY_TYPE_TRACKED_CACHE,
            title="GC12345",
            unique_id="GC12345",
        )
        hass.config_entries.async_add_subentry(mock_config_entry, subentry)
        await hass.async_block_till_done()

        async_schedule_reload.assert_called_once_with(mock_config_entry.entry_id)

        hass.config_entries.async_remove_subentry(
            mock_config_entry, subentry.subentry_id
        )
        await hass.async_block_till_done()

    assert async_schedule_reload.call_count == 2


async def test_subentry_added_during_initial_refresh_schedules_reload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test subentries added during the first refresh are not missed."""
    mock_config_entry.add_to_hass(hass)
    coordinator = MagicMock()
    coordinator.subentry_ids = frozenset()

    async def add_subentry_during_refresh() -> None:
        hass.config_entries.async_add_subentry(
            mock_config_entry,
            ConfigSubentry(
                data=MappingProxyType({CONF_CODE: "GC12345"}),
                subentry_type=SUBENTRY_TYPE_TRACKED_CACHE,
                title="GC12345",
                unique_id="GC12345",
            ),
        )

    coordinator.async_config_entry_first_refresh = AsyncMock(
        side_effect=add_subentry_during_refresh
    )

    with (
        patch(
            "homeassistant.components.geocaching.async_get_config_entry_implementation",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.geocaching.OAuth2Session",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.geocaching.GeocachingDataUpdateCoordinator",
            return_value=coordinator,
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
        ),
        patch.object(
            hass.config_entries, "async_schedule_reload"
        ) as async_schedule_reload,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED
        async_schedule_reload.assert_called_once_with(mock_config_entry.entry_id)

        await async_update_entry(hass, mock_config_entry)
        async_schedule_reload.assert_called_once_with(mock_config_entry.entry_id)


async def test_oauth_token_refresh_does_not_reload_entry(
    hass: HomeAssistant,
) -> None:
    """Test a normal OAuth token refresh does not reload the config entry."""
    mock_config_entry = MockConfigEntry(
        title="1234AB 1",
        domain=DOMAIN,
        data={
            "id": "mock_user",
            "auth_implementation": DOMAIN,
            "token": {
                "access_token": "expired-token",
                "refresh_token": "refresh-token",
                "expires_at": 0,
            },
        },
        unique_id="mock_user",
    )
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    mock_config_entry.runtime_data = MagicMock()
    mock_config_entry.runtime_data.subentry_ids = frozenset()
    mock_config_entry.add_update_listener(async_update_entry)

    implementation = MagicMock()
    implementation.async_refresh_token = AsyncMock(
        return_value={
            "access_token": "new-token",
            "refresh_token": "refresh-token",
            "expires_at": 4_102_444_800,
        }
    )
    session = OAuth2Session(hass, mock_config_entry, implementation)

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as async_schedule_reload:
        await session.async_ensure_token_valid()
        await hass.async_block_till_done()

    assert mock_config_entry.data["token"]["access_token"] == "new-token"
    async_schedule_reload.assert_not_called()
