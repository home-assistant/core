"""Tests for the Vistapool integration setup and unload."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from aioaquarite import AquariteError, AuthenticationError
import pytest

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.vistapool.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import MOCK_POOL_ID, MOCK_POOL_NAME

from tests.common import MockConfigEntry

_SECOND_POOL_ID = "ZYXWVU9876543210"
_SECOND_POOL_NAME = "Spa"
_THIRD_POOL_ID = "QQQQQQ1111111111"
_TEMPERATURE_ENTITY = "sensor.my_pool_temperature"
_LIGHT_ENTITY = "light.my_pool_light"


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


async def test_unload_closes_firestore_clients(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_auth: MagicMock,
    mock_vistapool_client: AsyncMock,
) -> None:
    """Test unloading releases the Firestore gRPC channels."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    mock_vistapool_auth.close.assert_not_called()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vistapool_auth.close.assert_called_once()


@pytest.mark.parametrize(
    ("owner", "method", "exception"),
    [
        pytest.param("auth", "authenticate", AuthenticationError, id="auth_rejected"),
        pytest.param("auth", "authenticate", AquariteError, id="auth_unreachable"),
        pytest.param("client", "get_pools", AquariteError, id="pools_unreachable"),
    ],
)
async def test_failed_setup_closes_firestore_clients(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_vistapool_auth: MagicMock,
    mock_vistapool_client: AsyncMock,
    owner: str,
    method: str,
    exception: type[Exception],
) -> None:
    """Test a setup that never completes still releases the Firestore channels."""
    mocks = {"auth": mock_vistapool_auth, "client": mock_vistapool_client}
    getattr(mocks[owner], method).side_effect = exception
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_vistapool_auth.close.assert_called_once()
