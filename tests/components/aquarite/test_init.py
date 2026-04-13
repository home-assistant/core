"""Tests for the Aquarite integration setup and unload."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aioaquarite import AquariteError, AuthenticationError
import pytest

from homeassistant.components.aquarite.const import CONF_POOL_ID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .conftest import MOCK_PASSWORD, MOCK_POOL_ID, MOCK_POOL_NAME, MOCK_USERNAME

from tests.common import MockConfigEntry

PATCH_AUTH = "homeassistant.components.aquarite.AquariteAuth"
PATCH_CLIENT = "homeassistant.components.aquarite.AquariteClient"
PATCH_COORDINATOR = "homeassistant.components.aquarite.AquariteDataUpdateCoordinator"


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_POOL_NAME,
        data={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
            CONF_POOL_ID: MOCK_POOL_ID,
        },
        unique_id=MOCK_POOL_ID,
    )


def _make_coordinator(mock_pool_data: dict[str, Any]) -> MagicMock:
    """Build a mock coordinator that behaves like the real one."""
    coord = MagicMock()
    coord.async_config_entry_first_refresh = AsyncMock()
    coord.subscribe = AsyncMock()
    coord.setup_tasks = AsyncMock()
    coord.async_shutdown = AsyncMock()
    coord.data = mock_pool_data
    coord.pool_id = MOCK_POOL_ID
    return coord


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test successful setup of a config entry."""
    mock_entry.add_to_hass(hass)

    coord = _make_coordinator(mock_pool_data)

    with (
        patch(PATCH_AUTH) as mock_auth_cls,
        patch(PATCH_CLIENT),
        patch(PATCH_COORDINATOR, return_value=coord),
    ):
        mock_auth_cls.return_value = AsyncMock()
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.LOADED
    coord.async_config_entry_first_refresh.assert_awaited_once()
    coord.subscribe.assert_awaited_once()
    coord.setup_tasks.assert_awaited_once()


async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryAuthFailed on AuthenticationError."""
    mock_entry.add_to_hass(hass)

    with patch(PATCH_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth.authenticate.side_effect = AuthenticationError("bad creds")
        mock_auth_cls.return_value = mock_auth

        assert not await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_aquarite_error_during_auth(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
) -> None:
    """Test setup raises ConfigEntryNotReady on AquariteError during auth."""
    mock_entry.add_to_hass(hass)

    with patch(PATCH_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth.authenticate.side_effect = AquariteError("network down")
        mock_auth_cls.return_value = mock_auth

        assert not await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_aquarite_error_during_subscribe(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test setup raises ConfigEntryNotReady on AquariteError during subscribe."""
    mock_entry.add_to_hass(hass)

    coord = _make_coordinator(mock_pool_data)
    coord.subscribe = AsyncMock(side_effect=AquariteError("subscribe failed"))

    with (
        patch(PATCH_AUTH) as mock_auth_cls,
        patch(PATCH_CLIENT),
        patch(PATCH_COORDINATOR, return_value=coord),
    ):
        mock_auth_cls.return_value = AsyncMock()
        assert not await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_pool_data: dict[str, Any],
) -> None:
    """Test unload calls coordinator shutdown and clears state."""
    mock_entry.add_to_hass(hass)

    coord = _make_coordinator(mock_pool_data)

    with (
        patch(PATCH_AUTH) as mock_auth_cls,
        patch(PATCH_CLIENT),
        patch(PATCH_COORDINATOR, return_value=coord),
    ):
        mock_auth_cls.return_value = AsyncMock()
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.NOT_LOADED
    coord.async_shutdown.assert_awaited_once()
