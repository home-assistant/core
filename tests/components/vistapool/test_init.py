"""Tests for the Vistapool integration setup and unload."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from aioaquarite import AquariteError, AuthenticationError

from homeassistant.components.vistapool import async_remove_config_entry_device
from homeassistant.components.vistapool.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import MOCK_POOL_ID, MOCK_POOL_NAME

from tests.common import MockConfigEntry

_SECOND_POOL_ID = "ZYXWVU9876543210"
_SECOND_POOL_NAME = "Spa"
_THIRD_POOL_ID = "QQQQQQ1111111111"


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the integration sets up an entry end to end."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_auth: MagicMock,
) -> None:
    """Test setup ends in SETUP_ERROR on AuthenticationError."""
    mock_vistapool_auth.authenticate.side_effect = AuthenticationError
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_cannot_connect_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_auth: MagicMock,
) -> None:
    """Test setup retries on a transient AquariteError during auth."""
    mock_vistapool_auth.authenticate.side_effect = AquariteError("network")
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_cannot_connect_pools(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test setup retries on a transient AquariteError during get_pools."""
    mock_vistapool_client.get_pools.side_effect = AquariteError("fetch failed")
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_no_pools(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test setup ends in SETUP_ERROR when the account has no pools."""
    mock_vistapool_client.get_pools.return_value = {}
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_subscribe_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test setup retries when the per-pool Firestore subscription fails."""
    mock_vistapool_client.subscribe_pool_resilient.side_effect = AquariteError(
        "subscribe fail"
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_user_pools_subscribe_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test setup retries when the user-pools Firestore subscription fails."""
    mock_vistapool_client.subscribe_user_pools_resilient.side_effect = AquariteError(
        "user-pools subscribe fail"
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_user_pools_snapshot_adds_new_pool(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a user-pools snapshot containing a new pool adds a coordinator and device."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert set(mock_config_entry.runtime_data.coordinators) == {MOCK_POOL_ID}

    mock_vistapool_client.get_pools.return_value = {
        MOCK_POOL_ID: MOCK_POOL_NAME,
        _SECOND_POOL_ID: _SECOND_POOL_NAME,
    }
    snapshot_cb = mock_vistapool_client.subscribe_user_pools_resilient.call_args.args[0]
    snapshot_cb([MOCK_POOL_ID, _SECOND_POOL_ID])
    await hass.async_block_till_done()

    assert set(mock_config_entry.runtime_data.coordinators) == {
        MOCK_POOL_ID,
        _SECOND_POOL_ID,
    }
    assert device_registry.async_get_device(identifiers={(DOMAIN, _SECOND_POOL_ID)})


async def test_user_pools_snapshot_retries_new_pool_after_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a failed first refresh on a new pool is not orphaned and retries next snapshot."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vistapool_client.get_pools.return_value = {
        MOCK_POOL_ID: MOCK_POOL_NAME,
        _SECOND_POOL_ID: _SECOND_POOL_NAME,
    }
    mock_vistapool_client.fetch_pool_data.side_effect = AquariteError("refresh failed")
    snapshot_cb = mock_vistapool_client.subscribe_user_pools_resilient.call_args.args[0]
    snapshot_cb([MOCK_POOL_ID, _SECOND_POOL_ID])
    await hass.async_block_till_done()

    assert set(mock_config_entry.runtime_data.coordinators) == {MOCK_POOL_ID}

    mock_vistapool_client.fetch_pool_data.side_effect = None
    mock_vistapool_client.fetch_pool_data.return_value = {}
    snapshot_cb([MOCK_POOL_ID, _SECOND_POOL_ID])
    await hass.async_block_till_done()

    assert set(mock_config_entry.runtime_data.coordinators) == {
        MOCK_POOL_ID,
        _SECOND_POOL_ID,
    }


async def test_user_pools_snapshot_removes_stale_pool(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a user-pools snapshot missing a pool removes its coordinator and device."""
    mock_vistapool_client.get_pools.return_value = {
        MOCK_POOL_ID: MOCK_POOL_NAME,
        _SECOND_POOL_ID: _SECOND_POOL_NAME,
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get_device(identifiers={(DOMAIN, _SECOND_POOL_ID)})

    snapshot_cb = mock_vistapool_client.subscribe_user_pools_resilient.call_args.args[0]
    snapshot_cb([MOCK_POOL_ID])
    await hass.async_block_till_done()

    assert set(mock_config_entry.runtime_data.coordinators) == {MOCK_POOL_ID}
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, _SECOND_POOL_ID)})
        is None
    )


async def test_user_pools_snapshot_drops_stale_even_if_get_pools_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test stale pool removal still runs when get_pools() raises during reconcile."""
    mock_vistapool_client.get_pools.return_value = {
        MOCK_POOL_ID: MOCK_POOL_NAME,
        _SECOND_POOL_ID: _SECOND_POOL_NAME,
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert device_registry.async_get_device(identifiers={(DOMAIN, _SECOND_POOL_ID)})

    mock_vistapool_client.get_pools.side_effect = AquariteError("name lookup down")
    snapshot_cb = mock_vistapool_client.subscribe_user_pools_resilient.call_args.args[0]
    snapshot_cb([MOCK_POOL_ID, _THIRD_POOL_ID])
    await hass.async_block_till_done()

    # New pool skipped (no name available), stale pool removed regardless.
    assert set(mock_config_entry.runtime_data.coordinators) == {MOCK_POOL_ID}
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, _SECOND_POOL_ID)})
        is None
    )
    assert (
        device_registry.async_get_device(identifiers={(DOMAIN, _THIRD_POOL_ID)}) is None
    )


async def test_user_pools_snapshot_no_change_is_noop(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a snapshot matching the current set does not refetch pool names."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_vistapool_client.get_pools.reset_mock()

    snapshot_cb = mock_vistapool_client.subscribe_user_pools_resilient.call_args.args[0]
    snapshot_cb([MOCK_POOL_ID])
    await hass.async_block_till_done()

    mock_vistapool_client.get_pools.assert_not_called()


async def test_remove_config_entry_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test manual device removal is refused for active pools and allowed for stale ones."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    active_device = device_registry.async_get_device(
        identifiers={(DOMAIN, MOCK_POOL_ID)}
    )
    assert active_device is not None
    assert (
        await async_remove_config_entry_device(hass, mock_config_entry, active_device)
        is False
    )

    stale_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "stale-pool-id")},
    )
    assert (
        await async_remove_config_entry_device(hass, mock_config_entry, stale_device)
        is True
    )


async def test_apply_optimistic_creates_missing_intermediate_dicts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test apply_optimistic walks through and creates missing intermediate dicts."""
    mock_vistapool_client.fetch_pool_data.return_value = {"existing": "scalar"}
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = next(iter(mock_config_entry.runtime_data.coordinators.values()))
    coordinator.apply_optimistic("filtration.intel.temp", 27)
    coordinator.apply_optimistic("existing.nested.key", 1)

    assert coordinator.data["filtration"]["intel"]["temp"] == 27
    assert coordinator.data["existing"] == {"nested": {"key": 1}}


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the integration unloads cleanly."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
