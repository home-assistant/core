"""Tests for the Vistapool integration setup and unload."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from aioaquarite import AquariteError, AuthenticationError

from homeassistant.components.vistapool import coordinator as vp_coordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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
    """Test setup retries when the Firestore subscription fails."""
    mock_vistapool_client.subscribe_pool_resilient.side_effect = AquariteError(
        "subscribe fail"
    )
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


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


async def test_apply_optimistic_suppresses_stale_push(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a Firestore push that disagrees within the TTL is overlaid with the optimistic value."""
    mock_vistapool_client.fetch_pool_data.return_value = {"light": {"status": 0}}
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = next(iter(mock_config_entry.runtime_data.coordinators.values()))
    on_data = mock_vistapool_client.subscribe_pool_resilient.call_args.args[1]

    coordinator.apply_optimistic("light.status", 1)
    assert coordinator.data["light"]["status"] == 1

    on_data({"light": {"status": 0}})
    await hass.async_block_till_done()

    assert coordinator.data["light"]["status"] == 1


async def test_apply_optimistic_accepts_confirming_push(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a confirming push lets the protection expire so later disagreements stick."""
    mock_vistapool_client.fetch_pool_data.return_value = {"light": {"status": 0}}
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = next(iter(mock_config_entry.runtime_data.coordinators.values()))
    on_data = mock_vistapool_client.subscribe_pool_resilient.call_args.args[1]

    coordinator.apply_optimistic("light.status", 1)
    on_data({"light": {"status": "1"}})
    await hass.async_block_till_done()
    assert coordinator.data["light"]["status"] == "1"

    # Protection should have lifted; a later push (real off command) must stick.
    on_data({"light": {"status": 0}})
    await hass.async_block_till_done()
    assert coordinator.data["light"]["status"] == 0


async def test_apply_optimistic_yields_to_push_after_ttl(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a disagreeing Firestore push after the TTL window overrides the optimistic value."""
    mock_vistapool_client.fetch_pool_data.return_value = {"light": {"status": 0}}
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = next(iter(mock_config_entry.runtime_data.coordinators.values()))
    on_data = mock_vistapool_client.subscribe_pool_resilient.call_args.args[1]

    with patch.object(
        vp_coordinator,
        "monotonic",
        side_effect=[100.0, 100.0 + vp_coordinator.OPTIMISTIC_TTL_SECONDS + 1.0],
    ):
        coordinator.apply_optimistic("light.status", 1)
        on_data({"light": {"status": 0}})
        await hass.async_block_till_done()

    assert coordinator.data["light"]["status"] == 0


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
