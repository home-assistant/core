"""Test the ISEO Argo BLE lock entity."""

from unittest.mock import AsyncMock, MagicMock, patch

from iseo_argo_ble import IseoAuthError, IseoConnectionError
import pytest

from homeassistant.components.lock import LockState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
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
