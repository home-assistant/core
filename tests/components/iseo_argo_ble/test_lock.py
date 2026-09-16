"""Test the ISEO Argo BLE lock entity."""

import asyncio
from collections.abc import Generator
from datetime import timedelta
from unittest.mock import MagicMock, patch

from iseo_argo_ble import IseoAuthError, IseoConnectionError, LockState as IseoLockState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bluetooth.const import UNAVAILABLE_TRACK_SECONDS
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
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import inject_advertisement, setup_integration, trigger_poll

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.components.bluetooth import (
    patch_all_discovered_devices,
    patch_bluetooth_time,
)

ENTITY_ID = "lock.iseo_lock"


async def _unlock(hass: HomeAssistant) -> None:
    """Call the unlock action on the lock and let the relock task settle."""
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()


@pytest.fixture(autouse=True)
def _no_relock_delay() -> Generator[None]:
    """Run the relock bookkeeping without waiting for the real delays."""
    with (
        patch("homeassistant.components.iseo_argo_ble.lock.RELOCK_DELAY", 0),
        patch("homeassistant.components.iseo_argo_ble.lock.RELOCK_POLL_DELAY", 0),
    ):
        yield


@pytest.mark.usefixtures("mock_iseo_client")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the lock entity and its device."""
    with patch("homeassistant.components.iseo_argo_ble.PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_state_follows_door_status(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    lock_state: IseoLockState,
) -> None:
    """Test the reported state follows the door status read from the lock."""
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED

    lock_state.door_closed = False
    await trigger_poll(hass)

    assert hass.states.get(ENTITY_ID).state == LockState.UNLOCKED


async def test_unlock_keeps_unlocked_while_door_open(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    lock_state: IseoLockState,
) -> None:
    """Test an open door is not reported as locked after unlocking."""
    # The door is opened right after the latch is released.
    lock_state.door_closed = False

    await _unlock(hass)

    mock_iseo_client.gw_open.assert_called_once()
    assert hass.states.get(ENTITY_ID).state == LockState.UNLOCKED


@pytest.mark.usefixtures("config_entry")
async def test_unlock_reports_locked_once_door_is_closed(
    hass: HomeAssistant,
) -> None:
    """Test the lock reports locked again once the door is closed."""
    await _unlock(hass)

    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED


@pytest.mark.usefixtures("config_entry")
async def test_unlock_assumes_locked_when_door_status_disappears(
    hass: HomeAssistant,
    lock_state: IseoLockState,
) -> None:
    """Test the lock is assumed locked when it stops reporting door status."""
    lock_state.door_closed = None

    await _unlock(hass)

    state = hass.states.get(ENTITY_ID)
    assert state.state == LockState.LOCKED
    assert state.attributes[ATTR_ASSUMED_STATE] is True


@pytest.mark.usefixtures("config_entry")
async def test_unlock_assumes_locked_without_a_reading(
    hass: HomeAssistant,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the lock is assumed locked when the verification poll reads nothing."""
    mock_iseo_client.read_state.side_effect = IseoConnectionError("no link")

    await _unlock(hass)

    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED


@pytest.mark.usefixtures("mock_iseo_client")
async def test_unlock_relocks_without_door_status(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    lock_state: IseoLockState,
) -> None:
    """Test a lock without a door sensor reports locked again after unlocking."""
    lock_state.door_closed = None
    await setup_integration(hass, mock_config_entry)

    mock_iseo_client.read_state.reset_mock()
    await _unlock(hass)

    mock_iseo_client.gw_open.assert_called_once()
    # A lock without a door sensor is never connected to just to read state.
    mock_iseo_client.read_state.assert_not_called()
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED


@pytest.mark.usefixtures("config_entry")
async def test_lock_action_is_not_supported(hass: HomeAssistant) -> None:
    """Test locking on demand raises, the lock re-latches on its own."""
    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    assert excinfo.value.translation_key == "lock_not_supported"


@pytest.mark.usefixtures("config_entry")
async def test_unlock_rejected_identity(
    hass: HomeAssistant,
    mock_iseo_client: MagicMock,
) -> None:
    """Test unlocking raises when the lock rejects the stored identity."""
    mock_iseo_client.gw_open.side_effect = IseoAuthError("bad auth")

    with pytest.raises(HomeAssistantError) as excinfo:
        await _unlock(hass)

    assert excinfo.value.translation_key == "lock_rejected_identity"
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED


@pytest.mark.usefixtures("config_entry")
async def test_unlock_connection_error(
    hass: HomeAssistant,
    mock_iseo_client: MagicMock,
) -> None:
    """Test unlocking raises when the connection fails."""
    mock_iseo_client.gw_open.side_effect = IseoConnectionError("no link")

    with pytest.raises(HomeAssistantError) as excinfo:
        await _unlock(hass)

    assert excinfo.value.translation_key == "cannot_connect"
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED


@pytest.mark.usefixtures("config_entry")
async def test_unavailable_when_lock_stops_advertising(hass: HomeAssistant) -> None:
    """Test the lock is unavailable once it stops advertising."""
    assert hass.states.get(ENTITY_ID).state == LockState.LOCKED

    with (
        patch_bluetooth_time(
            dt_util.utcnow().timestamp() + UNAVAILABLE_TRACK_SECONDS + 1
        ),
        patch_all_discovered_devices([]),
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS + 1)
        )
        await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("config_entry")
async def test_poll_skipped_while_unlocking(
    hass: HomeAssistant,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the lock is not polled while a command holds the connection."""
    unlocking = asyncio.Event()
    finish = asyncio.Event()

    async def _blocking_open(**kwargs: object) -> None:
        unlocking.set()
        await finish.wait()

    mock_iseo_client.gw_open.side_effect = _blocking_open
    mock_iseo_client.read_state.reset_mock()

    unlock_task = hass.async_create_task(
        hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
    )
    await unlocking.wait()

    # The advertisement must not schedule a poll while the connection is busy.
    inject_advertisement(hass)
    await asyncio.sleep(0)
    mock_iseo_client.read_state.assert_not_called()

    finish.set()
    await unlock_task
    await hass.async_block_till_done()
