"""Tests for the Vistapool integration setup and unload."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from aioaquarite import AquariteError, AuthenticationError
import pytest

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE as NUMBER_SERVICE_SET_VALUE,
)
from homeassistant.components.vistapool import coordinator as vp_coordinator
from homeassistant.components.vistapool.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import MOCK_POOL_ID, MOCK_POOL_NAME

from tests.common import MockConfigEntry, async_fire_time_changed

_SECOND_POOL_ID = "ZYXWVU9876543210"
_SECOND_POOL_NAME = "Spa"
_THIRD_POOL_ID = "QQQQQQ1111111111"
_TEMPERATURE_ENTITY = "sensor.my_pool_temperature"
_LIGHT_ENTITY = "light.my_pool_light"
_INTEL_ENTITY = "number.my_pool_intel_temperature"


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
    """Test a user-pools snapshot with a new pool creates its device and entities."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.my_pool_temperature") is not None
    assert hass.states.get("sensor.spa_temperature") is None

    mock_vistapool_client.get_pools.return_value = {
        MOCK_POOL_ID: MOCK_POOL_NAME,
        _SECOND_POOL_ID: _SECOND_POOL_NAME,
    }
    snapshot_cb = mock_vistapool_client.subscribe_user_pools_resilient.call_args.args[0]
    snapshot_cb([MOCK_POOL_ID, _SECOND_POOL_ID])
    await hass.async_block_till_done()

    assert hass.states.get("sensor.spa_temperature") is not None
    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, _SECOND_POOL_ID), mock_config_entry.entry_id
    )


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

    assert hass.states.get("sensor.spa_temperature") is None

    mock_vistapool_client.fetch_pool_data.side_effect = None
    mock_vistapool_client.fetch_pool_data.return_value = {}
    snapshot_cb([MOCK_POOL_ID, _SECOND_POOL_ID])
    await hass.async_block_till_done()

    assert hass.states.get("sensor.spa_temperature") is not None


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


async def test_user_pools_snapshot_removes_stale_pool(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test a user-pools snapshot missing a pool removes its entities and device."""
    mock_vistapool_client.get_pools.return_value = {
        MOCK_POOL_ID: MOCK_POOL_NAME,
        _SECOND_POOL_ID: _SECOND_POOL_NAME,
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.spa_temperature") is not None

    snapshot_cb = mock_vistapool_client.subscribe_user_pools_resilient.call_args.args[0]
    snapshot_cb([MOCK_POOL_ID])
    await hass.async_block_till_done()

    assert hass.states.get("sensor.spa_temperature") is None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, _SECOND_POOL_ID), mock_config_entry.entry_id
        )
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
    assert hass.states.get("sensor.spa_temperature") is not None

    mock_vistapool_client.get_pools.side_effect = AquariteError("name lookup down")
    snapshot_cb = mock_vistapool_client.subscribe_user_pools_resilient.call_args.args[0]
    snapshot_cb([MOCK_POOL_ID, _THIRD_POOL_ID])
    await hass.async_block_till_done()

    # New pool skipped (no name available), stale pool removed regardless.
    assert hass.states.get("sensor.spa_temperature") is None
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, _THIRD_POOL_ID), mock_config_entry.entry_id
        )
        is None
    )


async def test_setup_prunes_devices_removed_while_offline(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test setup removes a leftover device for a pool no longer on the account."""
    mock_config_entry.add_to_hass(hass)
    stale_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, _SECOND_POOL_ID)},
    )
    assert stale_device is not None

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_POOL_ID), mock_config_entry.entry_id
    )
    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, _SECOND_POOL_ID), mock_config_entry.entry_id
        )
        is None
    )


async def test_optimistic_write_creates_missing_intermediate_dicts(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test writes through entities build or replace branches of the pool data.

    The fixture puts scalars where the write paths expect dicts, covering
    both a scalar at the branch root and a scalar intermediate node.
    """
    mock_vistapool_client.fetch_pool_data.return_value = {
        "light": "scalar",
        "filtration": {"intel": 5},
    }
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(_LIGHT_ENTITY).state == STATE_UNKNOWN
    assert hass.states.get(_INTEL_ENTITY).state == STATE_UNKNOWN

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY},
        blocking=True,
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        NUMBER_SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: _INTEL_ENTITY, ATTR_VALUE: 27},
        blocking=True,
    )

    assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON
    assert hass.states.get(_INTEL_ENTITY).state == "27.0"


@pytest.mark.parametrize(
    "remote_status",
    [
        pytest.param(0, id="numeric_disagreement"),
        pytest.param(None, id="non_coercible"),
    ],
)
async def test_optimistic_light_suppresses_stale_push(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
    remote_status: int | None,
) -> None:
    """Test a Firestore push that disagrees within the TTL keeps the light on."""
    mock_vistapool_client.fetch_pool_data.return_value = {"light": {"status": 0}}
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    on_data = mock_vistapool_client.subscribe_pool_resilient.call_args.args[1]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY},
        blocking=True,
    )
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON

    on_data({"light": {"status": remote_status}})
    await hass.async_block_till_done()

    assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON


async def test_optimistic_rapid_toggle_confirms_writes_in_order(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a push cannot confirm a later write while an earlier one is unconfirmed."""
    mock_vistapool_client.fetch_pool_data.return_value = {"light": {"status": 0}}
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    on_data = mock_vistapool_client.subscribe_pool_resilient.call_args.args[1]

    # Rapid toggle: ON then OFF, both awaiting their confirming pushes.
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY},
        blocking=True,
    )
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY},
        blocking=True,
    )
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_OFF

    # A pre-write echo carrying off matches the newest write but must not
    # lift protection while the on write is still unconfirmed.
    on_data({"light": {"status": 0}})
    await hass.async_block_till_done()
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_OFF

    # The on write's confirmation arrives; the light must not flip back on.
    on_data({"light": {"status": 1}})
    await hass.async_block_till_done()
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_OFF

    # The off write's confirmation clears protection; a later real push sticks.
    on_data({"light": {"status": 0}})
    await hass.async_block_till_done()
    on_data({"light": {"status": 1}})
    await hass.async_block_till_done()
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON


async def test_optimistic_light_accepts_confirming_push(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a confirming push lets the protection expire so later disagreements stick."""
    mock_vistapool_client.fetch_pool_data.return_value = {"light": {"status": 0}}
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    on_data = mock_vistapool_client.subscribe_pool_resilient.call_args.args[1]

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY},
        blocking=True,
    )
    on_data({"light": {"status": "1"}})
    await hass.async_block_till_done()
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON

    # Protection should have lifted; a later push (real off command) must stick.
    on_data({"light": {"status": 0}})
    await hass.async_block_till_done()
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_OFF


async def test_optimistic_light_yields_to_push_after_ttl(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a disagreeing Firestore push after the TTL window turns the light off."""
    mock_vistapool_client.fetch_pool_data.return_value = {"light": {"status": 0}}
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    on_data = mock_vistapool_client.subscribe_pool_resilient.call_args.args[1]

    with patch.object(
        vp_coordinator,
        "monotonic",
        side_effect=[100.0, 100.0 + vp_coordinator.OPTIMISTIC_TTL_SECONDS + 1.0],
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: _LIGHT_ENTITY},
            blocking=True,
        )
        on_data({"light": {"status": 0}})
        await hass.async_block_till_done()

    assert hass.states.get(_LIGHT_ENTITY).state == STATE_OFF


async def test_optimistic_writes_age_out_individually(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test each write ages out on its own timestamp, not the newest one.

    With coalesced snapshots that never match the oldest entry, the queue
    would otherwise stay alive as long as writes keep coming, suppressing
    real remote changes indefinitely.
    """
    mock_vistapool_client.fetch_pool_data.return_value = {"light": {"status": 0}}
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    on_data = mock_vistapool_client.subscribe_pool_resilient.call_args.args[1]
    ttl = vp_coordinator.OPTIMISTIC_TTL_SECONDS

    with patch.object(
        vp_coordinator,
        "monotonic",
        side_effect=[100.0, 104.0, 100.0 + ttl + 1.0, 104.0 + ttl + 1.0],
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: _LIGHT_ENTITY},
            blocking=True,
        )
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: _LIGHT_ENTITY},
            blocking=True,
        )
        assert hass.states.get(_LIGHT_ENTITY).state == STATE_OFF

        # The first write has aged out, but the newest one keeps its full
        # TTL: the remote on may not override the fresher off write yet.
        on_data({"light": {"status": 1}})
        await hass.async_block_till_done()
        assert hass.states.get(_LIGHT_ENTITY).state == STATE_OFF

        # Once the newest write has aged too, the remote change wins.
        on_data({"light": {"status": 1}})
        await hass.async_block_till_done()
        assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON


async def test_optimistic_light_self_expires_without_push(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the optimistic light state clears via the scheduled timer when no push arrives."""
    # Return a fresh dict per call so optimistic in-place mutation doesn't
    # leak back into the mock's payload on the next fetch.
    mock_vistapool_client.fetch_pool_data.side_effect = lambda *_a, **_k: {
        "light": {"status": 0}
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_vistapool_client.fetch_pool_data.reset_mock()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY},
        blocking=True,
    )
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON

    # The expiry is a raw loop timer, so force-fire scheduled handles instead
    # of waiting on wall-clock time.
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()

    mock_vistapool_client.fetch_pool_data.assert_called()
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_OFF


async def test_self_heal_retries_after_failed_fetch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test the self-heal fetch re-arms until an authoritative fetch succeeds."""
    mock_vistapool_client.fetch_pool_data.side_effect = lambda *_a, **_k: {
        "light": {"status": 0}
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY},
        blocking=True,
    )

    # The TTL expiry fires but the authoritative fetch fails.
    mock_vistapool_client.fetch_pool_data.side_effect = AquariteError("cloud down")
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_UNAVAILABLE

    # The re-armed retry succeeds once the cloud is reachable again.
    mock_vistapool_client.fetch_pool_data.side_effect = lambda *_a, **_k: {
        "light": {"status": 0}
    }
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_OFF


async def test_self_heal_stops_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test unloading the entry stops the self-heal retry loop."""
    mock_vistapool_client.fetch_pool_data.side_effect = lambda *_a, **_k: {
        "light": {"status": 0}
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY},
        blocking=True,
    )

    # The TTL expiry fires, the fetch fails, and a retry is armed.
    mock_vistapool_client.fetch_pool_data.side_effect = AquariteError("cloud down")
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_UNAVAILABLE

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # A leftover retry would refetch; the unload must have cancelled it.
    mock_vistapool_client.fetch_pool_data.reset_mock()
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()
    mock_vistapool_client.fetch_pool_data.assert_not_called()


async def test_manual_refresh_cancels_self_heal_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a successful manual refresh disarms the pending self-heal retry."""
    mock_vistapool_client.fetch_pool_data.side_effect = lambda *_a, **_k: {
        "light": {"status": 0}
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "homeassistant", {})

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY},
        blocking=True,
    )

    # The TTL expiry fires, the fetch fails, and a retry is armed.
    mock_vistapool_client.fetch_pool_data.side_effect = AquariteError("cloud down")
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_UNAVAILABLE

    # A manual refresh recovers; the armed retry must not refetch later.
    mock_vistapool_client.fetch_pool_data.side_effect = lambda *_a, **_k: {
        "light": {"status": 0}
    }
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: _LIGHT_ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_OFF

    mock_vistapool_client.fetch_pool_data.reset_mock()
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()
    mock_vistapool_client.fetch_pool_data.assert_not_called()


async def test_push_discards_in_flight_self_heal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test an authoritative push cancels an in-flight self-heal fetch."""
    mock_vistapool_client.fetch_pool_data.side_effect = lambda *_a, **_k: {
        "light": {"status": 0}
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    on_data = mock_vistapool_client.subscribe_pool_resilient.call_args.args[1]
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY},
        blocking=True,
    )

    # The TTL expiry fires and the self-heal fetch hangs mid-flight.
    release = asyncio.Event()

    async def _hanging_fetch(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        await release.wait()
        raise AquariteError("late failure")

    mock_vistapool_client.fetch_pool_data.reset_mock()
    mock_vistapool_client.fetch_pool_data.side_effect = _hanging_fetch
    async_fire_time_changed(hass, fire_all=True)
    for _ in range(5):
        await asyncio.sleep(0)
    assert mock_vistapool_client.fetch_pool_data.called

    # The push must win: the hung fetch's late failure may neither mark the
    # light unavailable nor re-arm the retry.
    on_data({"light": {"status": 0}})
    release.set()
    await hass.async_block_till_done()

    assert hass.states.get(_LIGHT_ENTITY).state == STATE_OFF

    mock_vistapool_client.fetch_pool_data.reset_mock()
    async_fire_time_changed(hass, fire_all=True)
    await hass.async_block_till_done()
    mock_vistapool_client.fetch_pool_data.assert_not_called()


async def test_push_supersedes_in_flight_manual_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a push landing during a manual refresh outranks the fetch result.

    The fetch read the document before the push's change, and the push may
    have consumed the pending write that would have protected against the
    older data; publishing the fetch would flip entities back.
    """
    mock_vistapool_client.fetch_pool_data.side_effect = lambda *_a, **_k: {
        "light": {"status": 0}
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "homeassistant", {})

    on_data = mock_vistapool_client.subscribe_pool_resilient.call_args.args[1]

    release = asyncio.Event()

    async def _slow_stale_fetch(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        await release.wait()
        return {"light": {"status": 0}}

    mock_vistapool_client.fetch_pool_data.reset_mock()
    mock_vistapool_client.fetch_pool_data.side_effect = _slow_stale_fetch
    refresh = hass.async_create_task(
        hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: _LIGHT_ENTITY},
            blocking=True,
        )
    )
    for _ in range(5):
        await asyncio.sleep(0)
    assert mock_vistapool_client.fetch_pool_data.called

    on_data({"light": {"status": 1}})
    for _ in range(5):
        await asyncio.sleep(0)
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON

    # The fetch completes with data read before the push; the push must win.
    release.set()
    await refresh
    await hass.async_block_till_done()

    assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON


async def test_push_supersedes_failed_in_flight_manual_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a manual refresh failing after a push does not mark data unavailable.

    The push already supplied fresh data; letting the late failure through
    would flip the entities to unavailable right after they updated.
    """
    mock_vistapool_client.fetch_pool_data.side_effect = lambda *_a, **_k: {
        "light": {"status": 0}
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "homeassistant", {})

    on_data = mock_vistapool_client.subscribe_pool_resilient.call_args.args[1]

    release = asyncio.Event()

    async def _slow_failing_fetch(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        await release.wait()
        raise AquariteError("late failure")

    mock_vistapool_client.fetch_pool_data.reset_mock()
    mock_vistapool_client.fetch_pool_data.side_effect = _slow_failing_fetch
    refresh = hass.async_create_task(
        hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: _LIGHT_ENTITY},
            blocking=True,
        )
    )
    for _ in range(5):
        await asyncio.sleep(0)
    assert mock_vistapool_client.fetch_pool_data.called

    on_data({"light": {"status": 1}})
    for _ in range(5):
        await asyncio.sleep(0)
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON

    # The fetch fails only after the push; the fresh data must stay available.
    release.set()
    await refresh
    await hass.async_block_till_done()

    assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON


async def test_self_heal_supersedes_in_flight_manual_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a self-heal publish during a manual refresh outranks the fetch result.

    The manual fetch read the document before the self-heal did; accepting
    its late result would overwrite the fresher data the self-heal
    published after the optimistic TTL expired.
    """
    mock_vistapool_client.fetch_pool_data.side_effect = lambda *_a, **_k: {
        "light": {"status": 0}
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "homeassistant", {})

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY},
        blocking=True,
    )

    release = asyncio.Event()
    calls: list[None] = []

    async def _manual_hangs_then_self_heal(
        *_args: Any, **_kwargs: Any
    ) -> dict[str, Any]:
        """The manual fetch hangs with a pre-write read; the self-heal reads fresh."""
        calls.append(None)
        if len(calls) == 1:
            await release.wait()
            return {"light": {"status": 0}}
        return {"light": {"status": 1}}

    mock_vistapool_client.fetch_pool_data.reset_mock()
    mock_vistapool_client.fetch_pool_data.side_effect = _manual_hangs_then_self_heal

    refresh = hass.async_create_task(
        hass.services.async_call(
            "homeassistant",
            "update_entity",
            {ATTR_ENTITY_ID: _LIGHT_ENTITY},
            blocking=True,
        )
    )
    for _ in range(5):
        await asyncio.sleep(0)
    assert len(calls) == 1

    # The TTL expiry drops the write and the self-heal publishes fresh data.
    async_fire_time_changed(hass, fire_all=True)
    for _ in range(5):
        await asyncio.sleep(0)
    assert len(calls) == 2
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON

    # The manual fetch completes with its older read; the self-heal must win.
    release.set()
    await refresh
    await hass.async_block_till_done()

    assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON


async def test_stale_push_cannot_confirm_newer_write_after_prune(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a snapshot that pruned an expired write cannot confirm the next one.

    With on and off queued at t=0 and t=4, a stale pre-write off snapshot
    at t=11 prunes the expired on; letting it also confirm the fresh off
    would clear the queue and let the delayed on echo flip the entity back.
    """
    mock_vistapool_client.fetch_pool_data.return_value = {"light": {"status": 0}}
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    on_data = mock_vistapool_client.subscribe_pool_resilient.call_args.args[1]
    ttl = vp_coordinator.OPTIMISTIC_TTL_SECONDS
    clock = {"now": 100.0}

    with patch.object(vp_coordinator, "monotonic", side_effect=lambda: clock["now"]):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: _LIGHT_ENTITY},
            blocking=True,
        )
        clock["now"] = 104.0
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: _LIGHT_ENTITY},
            blocking=True,
        )
        assert hass.states.get(_LIGHT_ENTITY).state == STATE_OFF

        # A stale pre-write echo lands after the on write expired.
        clock["now"] = 100.0 + ttl + 1.0
        on_data({"light": {"status": 0}})
        await hass.async_block_till_done()
        assert hass.states.get(_LIGHT_ENTITY).state == STATE_OFF

        # The delayed on echo must not flip the entity: the off write is
        # newer and still within its TTL.
        on_data({"light": {"status": 1}})
        await hass.async_block_till_done()
        assert hass.states.get(_LIGHT_ENTITY).state == STATE_OFF


async def test_refresh_preserves_other_pending_optimistic_values(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test a forced refresh keeps writes still inside their own TTL window."""
    mock_vistapool_client.fetch_pool_data.side_effect = lambda *_a, **_k: {
        "light": {"status": 0},
        "filtration": {"intel": {"temp": 24}},
    }
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "homeassistant", {})

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY},
        blocking=True,
    )
    await hass.services.async_call(
        NUMBER_DOMAIN,
        NUMBER_SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: _INTEL_ENTITY, ATTR_VALUE: 27},
        blocking=True,
    )

    # A manual refresh must not clobber writes that are still inside
    # their own TTL window.
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: _LIGHT_ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(_LIGHT_ENTITY).state == STATE_ON
    assert hass.states.get(_INTEL_ENTITY).state == "27.0"


async def test_entities_unavailable_while_push_connection_is_down(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test entities go unavailable when the Firestore subscription drops.

    The integration has no polling interval, so without this the last
    snapshot would stay on display as if it were still current.
    """
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(_TEMPERATURE_ENTITY).state != STATE_UNAVAILABLE

    call = mock_vistapool_client.subscribe_pool_resilient.call_args
    on_data = call.args[1]
    on_health = call.kwargs["on_health"]

    on_health(False)
    await hass.async_block_till_done()

    assert hass.states.get(_TEMPERATURE_ENTITY).state == STATE_UNAVAILABLE

    # Only an incoming snapshot proves the connection is back.
    on_data({"main": {"temperature": 25}})
    await hass.async_block_till_done()

    assert hass.states.get(_TEMPERATURE_ENTITY).state == "25.0"


async def test_entities_stay_unavailable_on_local_updates_during_outage(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test updates that are not push snapshots do not fake availability.

    Both an optimistic write and a manual refresh set the coordinator's
    success flag, so availability cannot ride on that flag alone.
    """
    mock_vistapool_client.fetch_pool_data.return_value = {"light": {"status": 0}}
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "homeassistant", {})

    on_health = mock_vistapool_client.subscribe_pool_resilient.call_args.kwargs[
        "on_health"
    ]
    on_health(False)
    await hass.async_block_till_done()
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_UNAVAILABLE

    # An optimistic write updates coordinator data while the push is down.
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: _LIGHT_ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_UNAVAILABLE

    # So does a successful manual refresh.
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {ATTR_ENTITY_ID: _LIGHT_ENTITY},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(_LIGHT_ENTITY).state == STATE_UNAVAILABLE


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
