"""Test the ISEO Argo BLE lock entity."""

from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from iseo_argo_ble import IseoAuthError, IseoConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.iseo_argo_ble.const import DOMAIN
from homeassistant.components.iseo_argo_ble.lock import _POLL_INTERVAL
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_UNLOCK,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "lock.iseo_lock"


def _lock_state(door_closed: bool | None) -> MagicMock:
    """Return a lock state reporting the given door status."""
    return MagicMock(door_closed=door_closed, firmware_info="FW:  1.2.3")


async def _unlock(hass: HomeAssistant) -> None:
    """Call the unlock action on the lock."""
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )


@pytest.mark.usefixtures("mock_iseo_client", "mock_derive_private_key")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
) -> None:
    """Test the lock entity and its device."""
    with patch("homeassistant.components.iseo_argo_ble.PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures(
    "mock_iseo_client", "mock_derive_private_key", "mock_ble_device"
)
async def test_firmware_version_is_reported(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the firmware version read from the lock lands on the device."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.unique_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "1.2.3"


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_state_follows_door_status(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the reported state follows the door status read from the lock."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED

    mock_iseo_client.read_state.return_value = _lock_state(door_closed=False)
    freezer.tick(_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == LockState.UNLOCKED


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unlock_keeps_unlocked_while_door_open(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test an open door is not reported as locked after unlocking."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED

    # The door is opened right after the latch is released.
    mock_iseo_client.read_state.return_value = _lock_state(door_closed=False)

    with patch("homeassistant.components.iseo_argo_ble.lock._RELOCK_POLL_DELAY", 0):
        await _unlock(hass)
        await hass.async_block_till_done()

    mock_iseo_client.gw_open.assert_called_once()
    assert hass.states.get(ENTITY_ID).state == LockState.UNLOCKED


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unlock_reports_locked_once_door_is_closed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the lock reports locked again once the door is closed."""
    await setup_integration(hass, mock_config_entry)

    with patch("homeassistant.components.iseo_argo_ble.lock._RELOCK_POLL_DELAY", 0):
        await _unlock(hass)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unlock_assumes_locked_without_a_reading(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the lock is assumed locked when the verification poll reads nothing."""
    await setup_integration(hass, mock_config_entry)

    # The lock stops reporting its door status while the latch is released.
    mock_iseo_client.read_state.return_value = _lock_state(door_closed=None)

    with patch("homeassistant.components.iseo_argo_ble.lock._RELOCK_POLL_DELAY", 0):
        await _unlock(hass)
        await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == LockState.LOCKED
    assert state.attributes[ATTR_ASSUMED_STATE] is True


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unlock_relocks_without_door_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test a lock without door status reports locked again after unlocking."""
    mock_iseo_client.read_state.return_value = _lock_state(door_closed=None)
    await setup_integration(hass, mock_config_entry)

    with patch("homeassistant.components.iseo_argo_ble.lock._RELOCK_DELAY", 0):
        await _unlock(hass)
        await hass.async_block_till_done()

    mock_iseo_client.gw_open.assert_called_once()
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED


@pytest.mark.usefixtures("mock_derive_private_key")
async def test_availability_recovers_without_door_status(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    mock_ble_device: MagicMock,
) -> None:
    """Test a lock without door status becomes available again after a dropout."""
    mock_iseo_client.read_state.return_value = _lock_state(door_closed=None)
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get(ENTITY_ID)
    assert state.state == LockState.LOCKED
    assert state.attributes[ATTR_ASSUMED_STATE] is True

    # The lock goes out of range and an unlock fails.
    with (
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await _unlock(hass)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    # It comes back into range.
    freezer.tick(_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_availability_recovers_after_read_error(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the lock becomes unavailable on read errors and recovers."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED

    mock_iseo_client.read_state.side_effect = IseoConnectionError("offline")
    freezer.tick(_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    mock_iseo_client.read_state.side_effect = None
    freezer.tick(_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unavailable_when_lock_rejects_identity(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the lock becomes unavailable when it rejects the stored identity."""
    await setup_integration(hass, mock_config_entry)

    mock_iseo_client.read_state.side_effect = IseoAuthError("rejected")
    freezer.tick(_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unavailable_when_device_is_not_seen(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the lock is unavailable while it is not advertising."""
    await setup_integration(hass, mock_config_entry)

    mock_iseo_client.read_state.reset_mock()
    with patch(
        "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
        return_value=None,
    ):
        freezer.tick(_POLL_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    mock_iseo_client.read_state.assert_not_called()


@pytest.mark.usefixtures(
    "mock_derive_private_key", "mock_iseo_client", "mock_ble_device"
)
async def test_lock_action_is_not_supported(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test locking on demand raises, the lock re-latches on its own."""
    await setup_integration(hass, mock_config_entry)

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert excinfo.value.translation_key == "lock_not_supported"


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unlock_rejected_identity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test unlocking raises when the lock rejects the identity."""
    await setup_integration(hass, mock_config_entry)

    mock_iseo_client.gw_open = AsyncMock(side_effect=IseoAuthError("bad auth"))

    with pytest.raises(HomeAssistantError) as excinfo:
        await _unlock(hass)

    assert excinfo.value.translation_key == "lock_rejected_identity"
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unlock_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test unlocking raises and marks unavailable when the connection fails."""
    await setup_integration(hass, mock_config_entry)

    mock_iseo_client.gw_open = AsyncMock(side_effect=IseoConnectionError("no link"))

    with pytest.raises(HomeAssistantError) as excinfo:
        await _unlock(hass)

    assert excinfo.value.translation_key == "cannot_connect"
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unlock_without_device_in_range(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test unlocking raises when the lock is not advertising."""
    await setup_integration(hass, mock_config_entry)

    with (
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError) as excinfo,
    ):
        await _unlock(hass)

    assert excinfo.value.translation_key == "cannot_connect"
    mock_iseo_client.gw_open.assert_not_called()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
