"""Tests for the Aquarite integration setup and unload."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aioaquarite import AquariteError, AuthenticationError
import pytest

from homeassistant.components.aquarite import (
    AquariteData,
    _periodic_health_check,
    _refresh_all_subscriptions,
    _token_refresh_loop,
)
from homeassistant.components.aquarite.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .conftest import (
    MOCK_PASSWORD,
    MOCK_POOL_ID,
    MOCK_POOL_NAME,
    MOCK_USER_ID,
    MOCK_USERNAME,
)

from tests.common import MockConfigEntry

PATCH_AUTH = "homeassistant.components.aquarite.AquariteAuth"
PATCH_CLIENT = "homeassistant.components.aquarite.AquariteClient"
PATCH_COORDINATOR = "homeassistant.components.aquarite.AquariteDataUpdateCoordinator"


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_USERNAME,
        data={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
        unique_id=MOCK_USER_ID,
    )


def _make_coordinator(pool_id: str, pool_name: str) -> MagicMock:
    """Build a mock coordinator with async lifecycle methods."""
    coord = MagicMock()
    coord.pool_id = pool_id
    coord.pool_name = pool_name
    coord.async_config_entry_first_refresh = AsyncMock()
    coord.subscribe = AsyncMock()
    coord.async_shutdown = AsyncMock()
    coord.refresh_subscription = AsyncMock()
    return coord


def _patch_setup(pools: dict[str, str], coord_factory: Any = None) -> Any:
    """Patch AquariteAuth, AquariteClient, and the coordinator constructor."""
    coords: dict[str, MagicMock] = {}

    def _make(_hass, _entry, _auth, _api, pool_id, pool_name):
        coord = (coord_factory or _make_coordinator)(pool_id, pool_name)
        coords[pool_id] = coord
        return coord

    api = AsyncMock()
    api.get_pools = AsyncMock(return_value=pools)

    auth = MagicMock()
    auth.authenticate = AsyncMock()
    auth.is_token_expiring = MagicMock(return_value=False)
    auth.calculate_sleep_duration = MagicMock(return_value=3600)
    auth.get_client = AsyncMock(return_value=(api, False))

    return (
        patch(PATCH_AUTH, return_value=auth),
        patch(PATCH_CLIENT, return_value=api),
        patch(PATCH_COORDINATOR, side_effect=_make),
        coords,
    )


async def test_setup_entry_success_single_pool(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Test successful setup of a config entry with one pool."""
    mock_entry.add_to_hass(hass)
    pools = {MOCK_POOL_ID: MOCK_POOL_NAME}
    patch_auth, patch_client, patch_coord, coords = _patch_setup(pools)

    with patch_auth, patch_client, patch_coord:
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.LOADED
    assert set(mock_entry.runtime_data.coordinators) == {MOCK_POOL_ID}
    coords[MOCK_POOL_ID].async_config_entry_first_refresh.assert_awaited_once()
    coords[MOCK_POOL_ID].subscribe.assert_awaited_once()


async def test_setup_entry_success_multiple_pools(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Test successful setup with multiple pools creates a coordinator per pool."""
    mock_entry.add_to_hass(hass)
    pools = {"pool_a": "Pool A", "pool_b": "Pool B", "pool_c": "Pool C"}
    patch_auth, patch_client, patch_coord, coords = _patch_setup(pools)

    with patch_auth, patch_client, patch_coord:
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.LOADED
    assert set(mock_entry.runtime_data.coordinators) == set(pools)
    for coord in coords.values():
        coord.async_config_entry_first_refresh.assert_awaited_once()
        coord.subscribe.assert_awaited_once()


async def test_setup_entry_auth_failed(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Test setup raises ConfigEntryError on AuthenticationError."""
    mock_entry.add_to_hass(hass)

    with patch(PATCH_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth.authenticate.side_effect = AuthenticationError
        mock_auth_cls.return_value = mock_auth

        assert not await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_aquarite_error_during_auth(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Test setup raises ConfigEntryNotReady on AquariteError during auth."""
    mock_entry.add_to_hass(hass)

    with patch(PATCH_AUTH) as mock_auth_cls:
        mock_auth = AsyncMock()
        mock_auth.authenticate.side_effect = AquariteError("network")
        mock_auth_cls.return_value = mock_auth

        assert not await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_aquarite_error_during_get_pools(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Test setup raises ConfigEntryNotReady on AquariteError when fetching pools."""
    mock_entry.add_to_hass(hass)

    api = AsyncMock()
    api.get_pools = AsyncMock(side_effect=AquariteError("fetch failed"))

    with (
        patch(PATCH_AUTH, return_value=AsyncMock()),
        patch(PATCH_CLIENT, return_value=api),
    ):
        assert not await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_no_pools(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Test setup raises ConfigEntryError when the account has no pools."""
    mock_entry.add_to_hass(hass)
    patch_auth, patch_client, patch_coord, _ = _patch_setup({})

    with patch_auth, patch_client, patch_coord:
        assert not await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_aquarite_error_during_subscribe(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """Test setup raises ConfigEntryNotReady when subscribe fails."""
    mock_entry.add_to_hass(hass)

    def _coord_factory(pool_id: str, pool_name: str) -> MagicMock:
        coord = _make_coordinator(pool_id, pool_name)
        coord.subscribe = AsyncMock(side_effect=AquariteError("subscribe fail"))
        return coord

    pools = {MOCK_POOL_ID: MOCK_POOL_NAME}
    patch_auth, patch_client, patch_coord, _ = _patch_setup(pools, _coord_factory)

    with patch_auth, patch_client, patch_coord:
        assert not await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(hass: HomeAssistant, mock_entry: MockConfigEntry) -> None:
    """Test unload cancels tasks and shuts down all coordinators."""
    mock_entry.add_to_hass(hass)
    pools = {"pool_a": "Pool A", "pool_b": "Pool B"}
    patch_auth, patch_client, patch_coord, coords = _patch_setup(pools)

    with patch_auth, patch_client, patch_coord:
        assert await hass.config_entries.async_setup(mock_entry.entry_id)
        await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_entry.state is ConfigEntryState.NOT_LOADED
    for coord in coords.values():
        coord.async_shutdown.assert_awaited_once()


# ── Background helpers ─────────────────────────────────────────


def _make_data(coordinators: dict[str, MagicMock] | None = None) -> AquariteData:
    """Build an AquariteData with a configured auth mock."""
    auth = MagicMock()
    auth.is_token_expiring = MagicMock(return_value=False)
    auth.calculate_sleep_duration = MagicMock(return_value=3600)
    auth.get_client = AsyncMock(return_value=(AsyncMock(), False))
    api = AsyncMock()
    data = AquariteData(auth=auth, api=api)
    if coordinators:
        data.coordinators.update(coordinators)
    return data


async def test_refresh_all_subscriptions_calls_each() -> None:
    """Every coordinator's `refresh_subscription` is awaited."""
    coord_a = MagicMock(refresh_subscription=AsyncMock())
    coord_b = MagicMock(refresh_subscription=AsyncMock())
    data = _make_data({"a": coord_a, "b": coord_b})

    await _refresh_all_subscriptions(data, "ctx")

    coord_a.refresh_subscription.assert_awaited_once()
    coord_b.refresh_subscription.assert_awaited_once()


async def test_refresh_all_subscriptions_logs_per_pool_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failing coordinator does not stop the others; the failure is logged."""
    coord_a = MagicMock(
        refresh_subscription=AsyncMock(side_effect=RuntimeError("nope"))
    )
    coord_b = MagicMock(refresh_subscription=AsyncMock())
    data = _make_data({"a": coord_a, "b": coord_b})

    await _refresh_all_subscriptions(data, "ctx")

    coord_a.refresh_subscription.assert_awaited_once()
    coord_b.refresh_subscription.assert_awaited_once()
    assert "Error refreshing subscription ctx" in caplog.text


async def test_token_refresh_loop_refreshes_on_expiry(hass: HomeAssistant) -> None:
    """Token refresh loop re-subscribes pools when the token was renewed."""
    coord = MagicMock(refresh_subscription=AsyncMock())
    data = _make_data({"a": coord})
    data.auth.is_token_expiring.return_value = True
    data.auth.get_client = AsyncMock(return_value=(AsyncMock(), True))

    # Break out of the loop after one iteration via the trailing sleep.
    async def fake_sleep(_delay: float) -> None:
        raise asyncio.CancelledError

    with (
        patch(
            "homeassistant.components.aquarite.asyncio.sleep", side_effect=fake_sleep
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await _token_refresh_loop(hass, data)

    data.auth.get_client.assert_awaited_once()
    coord.refresh_subscription.assert_awaited_once()


async def test_token_refresh_loop_logs_and_retries(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A failure in the body falls into the retry/backoff branch."""
    data = _make_data()
    data.auth.is_token_expiring.return_value = True
    data.auth.get_client = AsyncMock(side_effect=RuntimeError("boom"))

    async def fake_sleep(_delay: float) -> None:
        raise asyncio.CancelledError

    with (
        patch(
            "homeassistant.components.aquarite.asyncio.sleep", side_effect=fake_sleep
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await _token_refresh_loop(hass, data)

    assert "Error maintaining token" in caplog.text


async def test_periodic_health_check_resubscribes_on_error(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Health check resubscribes pools when `get_client` fails."""
    coord = MagicMock(refresh_subscription=AsyncMock())
    data = _make_data({"a": coord})
    data.auth.get_client = AsyncMock(side_effect=RuntimeError("offline"))

    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        # First sleep: let it through so the body runs once.
        # Second sleep: raise to break out of the while loop.
        sleep_calls.append(delay)
        if len(sleep_calls) >= 2:
            raise asyncio.CancelledError

    with (
        patch(
            "homeassistant.components.aquarite.asyncio.sleep", side_effect=fake_sleep
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await _periodic_health_check(hass, data)

    data.auth.get_client.assert_awaited_once()
    coord.refresh_subscription.assert_awaited_once()
    assert "Health check failed" in caplog.text
