"""Tests for tedee lock."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pytedee_async import TedeeLock
from pytedee_async.exception import (
    TedeeClientException,
    TedeeDataUpdateException,
    TedeeLocalAuthException,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    STATE_LOCKING,
    STATE_UNLOCKING,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_lock(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the tedee lock."""
    mock_tedee.lock.return_value = None
    mock_tedee.unlock.return_value = None
    mock_tedee.open.return_value = None

    state = hass.states.get("lock.lock_1a2b")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry == snapshot
    assert entry.device_id

    device = device_registry.async_get(entry.device_id)
    assert device == snapshot

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        {
            ATTR_ENTITY_ID: "lock.lock_1a2b",
        },
        blocking=True,
    )

    assert len(mock_tedee.lock.mock_calls) == 1
    mock_tedee.lock.assert_called_once_with(12345)
    state = hass.states.get("lock.lock_1a2b")
    assert state
    assert state.state == STATE_LOCKING

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        {
            ATTR_ENTITY_ID: "lock.lock_1a2b",
        },
        blocking=True,
    )

    assert len(mock_tedee.unlock.mock_calls) == 1
    mock_tedee.unlock.assert_called_once_with(12345)
    state = hass.states.get("lock.lock_1a2b")
    assert state
    assert state.state == STATE_UNLOCKING

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_OPEN,
        {
            ATTR_ENTITY_ID: "lock.lock_1a2b",
        },
        blocking=True,
    )

    assert len(mock_tedee.open.mock_calls) == 1
    mock_tedee.open.assert_called_once_with(12345)
    state = hass.states.get("lock.lock_1a2b")
    assert state
    assert state.state == STATE_UNLOCKING


async def test_lock_without_pullspring(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the tedee lock without pullspring."""
    mock_tedee.lock.return_value = None
    mock_tedee.unlock.return_value = None
    mock_tedee.open.return_value = None

    state = hass.states.get("lock.lock_2c3d")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry == snapshot

    assert entry.device_id
    device = device_registry.async_get(entry.device_id)
    assert device
    assert device == snapshot

    with pytest.raises(
        HomeAssistantError,
        match="Entity lock.lock_2c3d does not support this service.",
    ):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_OPEN,
            {
                ATTR_ENTITY_ID: "lock.lock_2c3d",
            },
            blocking=True,
        )

    assert len(mock_tedee.open.mock_calls) == 0


async def test_lock_errors(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
) -> None:
    """Test event errors."""
    mock_tedee.lock.side_effect = TedeeClientException("Boom")
    with pytest.raises(HomeAssistantError, match="Failed to lock the door. Lock 12345"):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {
                ATTR_ENTITY_ID: "lock.lock_1a2b",
            },
            blocking=True,
        )

    mock_tedee.unlock.side_effect = TedeeClientException("Boom")
    with pytest.raises(
        HomeAssistantError, match="Failed to unlock the door. Lock 12345"
    ):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {
                ATTR_ENTITY_ID: "lock.lock_1a2b",
            },
            blocking=True,
        )

    mock_tedee.open.side_effect = TedeeClientException("Boom")
    with pytest.raises(
        HomeAssistantError, match="Failed to unlatch the door. Lock 12345"
    ):
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_OPEN,
            {
                ATTR_ENTITY_ID: "lock.lock_1a2b",
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    "side_effect",
    [
        TedeeClientException("Boom"),
        TedeeLocalAuthException("Boom"),
        TimeoutError,
        TedeeDataUpdateException("Boom"),
    ],
)
async def test_update_failed(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    freezer: FrozenDateTimeFactory,
    side_effect: Exception,
) -> None:
    """Test update failed."""
    mock_tedee.sync.side_effect = side_effect
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("lock.lock_1a2b")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_cleanup_removed_locks(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure removed locks are cleaned up."""

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    locks = [device.name for device in devices]
    assert "Lock-1A2B" in locks

    # remove a lock and wait for coordinator
    mock_tedee.locks_dict.pop(12345)
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    devices = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )

    locks = [device.name for device in devices]
    assert "Lock-1A2B" not in locks


async def test_new_lock(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure new lock is added automatically."""

    state = hass.states.get("lock.lock_4e5f")
    assert state is None

    mock_tedee.locks_dict[666666] = TedeeLock("Lock-4E5F", 666666, 2)
    mock_tedee.locks_dict[777777] = TedeeLock(
        "Lock-6G7H",
        777777,
        4,
        is_enabled_pullspring=True,
    )

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("lock.lock_4e5f")
    assert state
    state = hass.states.get("lock.lock_6g7h")
    assert state
