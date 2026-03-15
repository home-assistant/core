"""Test the ISEO Argo BLE lock entity."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

from iseo_argo_ble import IseoAuthError, IseoConnectionError
import pytest

from homeassistant.components.iseo_argo_ble.const import DOMAIN
from homeassistant.components.iseo_argo_ble.lock import _POLL_INTERVAL, IseoLockEntity
from homeassistant.components.lock import LockState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity_component import EntityComponent

from tests.common import MockConfigEntry


async def _setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.iseo_argo_ble.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


async def test_lock_is_initially_locked(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that the lock entity starts in the locked state."""
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )

    all_locks = [s for s in hass.states.async_all() if s.domain == "lock"]
    assert len(all_locks) == 1
    assert all_locks[0].state == LockState.LOCKED


async def test_unlock_calls_gw_open(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that calling unlock invokes gw_open on the IseoClient."""
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )

    all_locks = [s for s in hass.states.async_all() if s.domain == "lock"]
    assert len(all_locks) == 1
    lock_entity_id = all_locks[0].entity_id

    with patch(
        "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
        return_value=MagicMock(),
    ):
        await hass.services.async_call(
            "lock",
            "unlock",
            {"entity_id": lock_entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()

    mock_iseo_client.gw_open.assert_called_once()


async def test_unlock_auth_error_raises_ha_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that IseoAuthError during unlock raises HomeAssistantError."""
    mock_iseo_client.gw_open = AsyncMock(side_effect=IseoAuthError("bad auth"))

    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )

    all_locks = [s for s in hass.states.async_all() if s.domain == "lock"]
    lock_entity_id = all_locks[0].entity_id

    with (
        pytest.raises(HomeAssistantError),
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
    ):
        await hass.services.async_call(
            "lock",
            "unlock",
            {"entity_id": lock_entity_id},
            blocking=True,
        )


async def test_unlock_connection_error_raises_ha_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that IseoConnectionError during unlock raises HomeAssistantError."""
    mock_iseo_client.gw_open = AsyncMock(
        side_effect=IseoConnectionError("no connection")
    )

    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )

    all_locks = [s for s in hass.states.async_all() if s.domain == "lock"]
    lock_entity_id = all_locks[0].entity_id

    with (
        pytest.raises(HomeAssistantError),
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
    ):
        await hass.services.async_call(
            "lock",
            "unlock",
            {"entity_id": lock_entity_id},
            blocking=True,
        )

    # Verify it was marked unavailable
    state = hass.states.get(lock_entity_id)
    assert state.state == STATE_UNAVAILABLE


async def test_poll_state_no_ble_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that _poll_state handles None ble_device."""
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )

    # Get the entity from the component
    component: EntityComponent = hass.data["lock"]
    lock_entity = next(iter(component.entities))

    mock_iseo_client.read_state.reset_mock()

    assert lock_entity.available is True

    with patch(
        "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
        return_value=None,
    ):
        # This should not raise an exception, but catch IseoConnectionError and return
        await lock_entity._poll_state()

    mock_iseo_client.read_state.assert_not_called()
    assert lock_entity.available is False


async def test_poll_state_error_marks_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that _poll_state marks entity as unavailable on communication error."""
    # Allow setup to succeed with a valid state
    mock_iseo_client.read_state = AsyncMock(
        return_value=MagicMock(door_closed=True, firmware_info=None)
    )
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )

    component: EntityComponent = hass.data["lock"]
    lock_entity = next(iter(component.entities))

    assert lock_entity.available is True

    # Now make it fail
    mock_iseo_client.read_state = AsyncMock(side_effect=IseoConnectionError("offline"))
    with patch(
        "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
        return_value=MagicMock(),
    ):
        await lock_entity._poll_state()

    assert lock_entity.available is False


async def test_poll_state_success_marks_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that _poll_state marks entity as available on successful communication."""
    # Start with a failure during setup
    mock_iseo_client.read_state = AsyncMock(side_effect=IseoConnectionError("offline"))
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )

    component: EntityComponent = hass.data["lock"]
    lock_entity = next(iter(component.entities))

    # _setup_integration calls async_setup_entry which forwards setups,
    # and IseoLockEntity.async_added_to_hass calls _poll_state().
    assert lock_entity.available is False

    mock_iseo_client.read_state = AsyncMock(
        return_value=MagicMock(door_closed=True, firmware_info=None)
    )
    with patch(
        "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
        return_value=MagicMock(),
    ):
        await lock_entity._poll_state()
    assert lock_entity.available is True


async def test_lock_raises_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that async_lock raises HomeAssistantError."""
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )

    all_locks = [s for s in hass.states.async_all() if s.domain == "lock"]
    lock_entity_id = all_locks[0].entity_id

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            "lock",
            "lock",
            {"entity_id": lock_entity_id},
            blocking=True,
        )

    assert excinfo.value.translation_key == "lock_not_supported"


async def test_unlock_no_ble_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that unlock raises HomeAssistantError when ble_device is None."""
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )

    all_locks = [s for s in hass.states.async_all() if s.domain == "lock"]
    lock_entity_id = all_locks[0].entity_id

    with (
        pytest.raises(HomeAssistantError) as excinfo,
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
            return_value=None,
        ),
    ):
        await hass.services.async_call(
            "lock",
            "unlock",
            {"entity_id": lock_entity_id},
            blocking=True,
        )

    assert excinfo.value.translation_key == "cannot_connect"
    mock_iseo_client.gw_open.assert_not_called()

    # Verify it was marked unavailable
    state = hass.states.get(lock_entity_id)
    assert state.state == STATE_UNAVAILABLE


async def test_auto_relock_fallback_when_poll_exits_early(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test _auto_relock falls back to locked when _poll_state exits early."""
    mock_iseo_client.read_state = AsyncMock(
        return_value=MagicMock(door_closed=True, firmware_info=None)
    )
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )

    component: EntityComponent = hass.data["lock"]
    lock_entity = next(iter(component.entities))
    assert lock_entity._door_status_supported is True

    # Simulate state after a successful unlock
    lock_entity._attr_is_locked = False
    lock_entity._attr_is_unlocking = False

    # _poll_state exits early without updating _attr_is_locked
    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch.object(lock_entity, "_poll_state", new_callable=AsyncMock),
    ):
        await lock_entity._auto_relock()

    assert lock_entity._attr_is_locked is True


async def test_auto_relock_no_fallback_when_poll_updates_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test _auto_relock does not double-set state when _poll_state updates it."""
    mock_iseo_client.read_state = AsyncMock(
        return_value=MagicMock(door_closed=True, firmware_info=None)
    )
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )

    component: EntityComponent = hass.data["lock"]
    lock_entity = next(iter(component.entities))
    assert lock_entity._door_status_supported is True

    lock_entity._attr_is_locked = False
    lock_entity._attr_is_unlocking = False

    async def poll_sets_locked(*args: object, **kwargs: object) -> None:
        lock_entity._attr_is_locked = True

    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch.object(lock_entity, "_poll_state", side_effect=poll_sets_locked),
    ):
        await lock_entity._auto_relock()

    assert lock_entity._attr_is_locked is True


async def test_relock_task_cancellation(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test relock task cancellation."""
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )
    component: EntityComponent = hass.data["lock"]
    lock_entity = next(iter(component.entities))

    mock_task = MagicMock()
    mock_task.done.return_value = False
    lock_entity._relock_task = mock_task

    # Test _cancel_relock_task
    lock_entity._cancel_relock_task()
    mock_task.cancel.assert_called_once()

    # Test cancellation in async_unlock
    mock_task.cancel.reset_mock()
    with patch(
        "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
        return_value=MagicMock(),
    ):
        await lock_entity.async_unlock()
    mock_task.cancel.assert_called_once()


async def test_poll_state_locked_mutex(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test _poll_state early return when lock is already in use."""
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )
    component: EntityComponent = hass.data["lock"]
    lock_entity = next(iter(component.entities))

    mock_iseo_client.read_state.reset_mock()
    with patch.object(lock_entity._ble_lock, "locked", return_value=True):
        await lock_entity._poll_state()
        mock_iseo_client.read_state.assert_not_called()


async def test_poll_state_firmware_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test firmware version reporting in poll_state."""
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )
    component: EntityComponent = hass.data["lock"]
    lock_entity = next(iter(component.entities))

    # Reset initial setup state
    lock_entity._fw_version_set = False
    mock_iseo_client.read_state = AsyncMock(
        return_value=MagicMock(door_closed=True, firmware_info="FW:  1.2.3")
    )

    with (
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.helpers.device_registry.DeviceRegistry.async_get_device",
            return_value=None,
        ),
    ):
        await lock_entity._poll_state()

    # Should NOT be set because device was not found
    assert lock_entity._fw_version_set is False

    # Second poll with device present
    with patch(
        "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
        return_value=MagicMock(),
    ):
        await lock_entity._poll_state()

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device is not None
    assert device.sw_version == "1.2.3"
    assert lock_entity._fw_version_set is True


async def test_poll_state_early_returns(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test early returns in _poll_state (unlocking and suppress)."""
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )
    component: EntityComponent = hass.data["lock"]
    lock_entity = next(iter(component.entities))

    # Case 1: _attr_is_unlocking is True
    lock_entity._attr_is_unlocking = True
    mock_iseo_client.read_state.reset_mock()
    with patch(
        "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
        return_value=MagicMock(),
    ):
        await lock_entity._poll_state()
    # read_state is called BEFORE the check
    mock_iseo_client.read_state.assert_called()

    # Case 2: _poll_suppress_until is in the future
    lock_entity._attr_is_unlocking = False
    lock_entity._poll_suppress_until = datetime.now(tz=UTC) + timedelta(hours=1)
    mock_iseo_client.read_state.reset_mock()
    with patch(
        "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
        return_value=MagicMock(),
    ):
        await lock_entity._poll_state()
    mock_iseo_client.read_state.assert_called()


async def test_auto_relock_cancelled(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test _auto_relock handles cancellation."""
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )
    component: EntityComponent = hass.data["lock"]
    lock_entity = next(iter(component.entities))

    with patch("asyncio.sleep", side_effect=asyncio.CancelledError):
        # Should not raise
        await lock_entity._auto_relock()


async def test_poll_state_status_updates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test various status update branches in _poll_state."""
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )
    component: EntityComponent = hass.data["lock"]
    lock_entity = next(iter(component.entities))

    # Case: new_locked != self._attr_is_locked
    lock_entity._attr_is_locked = True
    mock_iseo_client.read_state = AsyncMock(
        return_value=MagicMock(door_closed=False, firmware_info=None)
    )
    with patch(
        "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
        return_value=MagicMock(),
    ):
        await lock_entity._poll_state()
    assert lock_entity._attr_is_locked is False

    # Case: _attr_is_unlocking is True early return branch
    lock_entity._attr_is_unlocking = True
    # We need to make it available first if it was unavailable to trigger the branch
    lock_entity._attr_available = False
    with patch(
        "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
        return_value=MagicMock(),
    ):
        await lock_entity._poll_state()
    assert lock_entity.available is True

    # Case: _poll_suppress_until early return branch
    lock_entity._attr_is_unlocking = False
    lock_entity._poll_suppress_until = datetime.now(tz=UTC) + timedelta(hours=1)
    lock_entity._attr_available = False
    with patch(
        "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
        return_value=MagicMock(),
    ):
        await lock_entity._poll_state()
    assert lock_entity.available is True


async def test_polling_scheduled_even_if_initial_poll_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that polling is scheduled even if the initial poll fails."""
    # initial _poll_state will fail
    mock_iseo_client.read_state = AsyncMock(side_effect=IseoConnectionError("offline"))

    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_track_time_interval"
        ) as mock_track,
        patch(
            "homeassistant.components.iseo_argo_ble.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        component: EntityComponent = hass.data["lock"]
        lock_entity = next(iter(component.entities))
        lock_entity = cast(IseoLockEntity, lock_entity)

        # Currently this will fail because _door_status_supported is None
        assert lock_entity._door_status_supported is None
        # Verify if async_track_time_interval was called
        # It should be called with (hass, lock_entity._poll_state, _POLL_INTERVAL)
        mock_track.assert_called_once_with(
            hass, lock_entity._poll_state, _POLL_INTERVAL
        )


async def test_polling_cancelled_if_unsupported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that polling is cancelled if door status is unsupported."""
    # initial _poll_state will fail, so it starts polling
    mock_iseo_client.read_state = AsyncMock(side_effect=IseoConnectionError("offline"))

    mock_config_entry.add_to_hass(hass)

    mock_unsub = MagicMock()

    with (
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_track_time_interval",
            return_value=mock_unsub,
        ),
        patch(
            "homeassistant.components.iseo_argo_ble.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        component: EntityComponent = hass.data["lock"]
        lock_entity = next(iter(component.entities))
        lock_entity = cast(IseoLockEntity, lock_entity)

        assert lock_entity._poll_unsub == mock_unsub

        # Now make _poll_state succeed but return door_closed=None (unsupported)
        mock_iseo_client.read_state = AsyncMock(
            return_value=MagicMock(door_closed=None, firmware_info=None)
        )
        await lock_entity._poll_state()

        assert lock_entity._door_status_supported is False
        assert lock_entity._poll_unsub is None
        mock_unsub.assert_called_once()


async def test_poll_state_ble_locked_manual_with_now(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test _poll_state early return when lock is already in use (coverage for line 106)."""
    await _setup_integration(
        hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
    )
    component: EntityComponent = hass.data["lock"]
    lock_entity = next(iter(component.entities))

    mock_iseo_client.read_state.reset_mock()
    with patch.object(lock_entity._ble_lock, "locked", return_value=True):
        await lock_entity._poll_state(_now=datetime.now(tz=UTC))
        mock_iseo_client.read_state.assert_not_called()
