"""Test the ISEO Argo BLE lock entity."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from iseo_argo_ble import IseoAuthError, IseoConnectionError
import pytest

from homeassistant.components import bluetooth
from homeassistant.components.iseo_argo_ble.const import DOMAIN
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


async def test_passive_scanning_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that the lock state is updated via passive scanning."""
    with patch(
        "homeassistant.components.bluetooth.async_register_callback",
        return_value=MagicMock(),
    ) as mock_register:
        await _setup_integration(
            hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
        )
        mock_register.assert_called_once()
        callback = mock_register.call_args[0][1]

    component: EntityComponent = hass.data["lock"]
    lock_entity = next(iter(component.entities))
    assert lock_entity.state == LockState.LOCKED

    # Simulate a bluetooth event with door open
    service_info = MagicMock()
    service_info.service_uuids = ["0000f000-0000-1000-8000-00805f9b34fb"]

    with patch(
        "homeassistant.components.iseo_argo_ble.lock.parse_iseo_advertisement",
        return_value=MagicMock(door_closed=False),
    ) as mock_parse:
        callback(service_info, bluetooth.BluetoothChange.ADVERTISEMENT)
        await hass.async_block_till_done()
        mock_parse.assert_called_once_with(service_info.service_uuids)

    assert hass.states.get(lock_entity.entity_id).state == LockState.UNLOCKED

    # Simulate a bluetooth event with door closed
    with patch(
        "homeassistant.components.iseo_argo_ble.lock.parse_iseo_advertisement",
        return_value=MagicMock(door_closed=True),
    ):
        callback(service_info, bluetooth.BluetoothChange.ADVERTISEMENT)
        await hass.async_block_till_done()

    assert hass.states.get(lock_entity.entity_id).state == LockState.LOCKED


async def test_initial_state_fetch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that initial state is fetched correctly."""
    mock_iseo_client.read_state = AsyncMock(
        return_value=MagicMock(door_closed=False, firmware_info="FW: 1.2.3")
    )

    # We need to await the task created in async_added_to_hass
    original_create_task = hass.async_create_task
    tasks = []

    def mock_create_task(coro, name=None):
        task = original_create_task(coro, name=name)
        tasks.append(task)
        return task

    with patch.object(hass, "async_create_task", side_effect=mock_create_task):
        await _setup_integration(
            hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
        )
        await asyncio.gather(*tasks)

    all_locks = [s for s in hass.states.async_all() if s.domain == "lock"]
    assert len(all_locks) == 1
    lock_entity_id = all_locks[0].entity_id
    assert hass.states.get(lock_entity_id).state == LockState.UNLOCKED

    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device is not None
    assert device.sw_version == "1.2.3"


async def test_initial_state_fetch_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_derive_private_key: MagicMock,
) -> None:
    """Test that initial state fetch failure is handled."""
    mock_iseo_client.read_state = AsyncMock(side_effect=IseoConnectionError("offline"))

    original_create_task = hass.async_create_task
    tasks = []

    def mock_create_task(coro, name=None):
        task = original_create_task(coro, name=name)
        tasks.append(task)
        return task

    with patch.object(hass, "async_create_task", side_effect=mock_create_task):
        await _setup_integration(
            hass, mock_config_entry, mock_iseo_client, mock_derive_private_key
        )
        await asyncio.gather(*tasks)

    all_locks = [s for s in hass.states.async_all() if s.domain == "lock"]
    assert len(all_locks) == 1
    lock_entity_id = all_locks[0].entity_id
    # Should stay locked (default)
    assert hass.states.get(lock_entity_id).state == LockState.LOCKED
