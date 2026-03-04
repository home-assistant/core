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

    with patch(
        "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
        return_value=None,
    ):
        # This should not raise an exception, but catch IseoConnectionError and return
        await lock_entity._poll_state()

    mock_iseo_client.read_state.assert_not_called()


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
