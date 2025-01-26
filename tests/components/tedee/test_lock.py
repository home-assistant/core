"""Tests for tedee lock."""

from datetime import timedelta
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse

from aiotedee import TedeeLock, TedeeLockState
from aiotedee.exception import (
    TedeeClientException,
    TedeeDataUpdateException,
    TedeeLocalAuthException,
)
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lock import (
    DOMAIN as LOCK_DOMAIN,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    LockState,
)
from homeassistant.components.webhook import async_generate_url
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceNotSupported
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from . import setup_integration
from .conftest import WEBHOOK_ID

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform
from tests.typing import ClientSessionGenerator


async def test_locks(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test tedee locks."""
    with patch("homeassistant.components.tedee.PLATFORMS", [Platform.LOCK]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_lock_service_calls(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
) -> None:
    """Test the tedee lock."""

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
    assert state.state == LockState.LOCKING

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
    assert state.state == LockState.UNLOCKING

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
    assert state.state == LockState.UNLOCKING


@pytest.mark.usefixtures("init_integration")
async def test_lock_without_pullspring(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the tedee lock without pullspring."""
    # Fetch translations
    await async_setup_component(hass, "homeassistant", {})

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
        ServiceNotSupported,
        match=f"Entity lock.lock_2c3d does not support action {LOCK_DOMAIN}.{SERVICE_OPEN}",
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


@pytest.mark.usefixtures("init_integration")
async def test_lock_errors(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
) -> None:
    """Test event errors."""
    mock_tedee.lock.side_effect = TedeeClientException("Boom")
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_LOCK,
            {
                ATTR_ENTITY_ID: "lock.lock_1a2b",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "lock_failed"

    mock_tedee.unlock.side_effect = TedeeClientException("Boom")
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_UNLOCK,
            {
                ATTR_ENTITY_ID: "lock.lock_1a2b",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "unlock_failed"

    mock_tedee.open.side_effect = TedeeClientException("Boom")
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            LOCK_DOMAIN,
            SERVICE_OPEN,
            {
                ATTR_ENTITY_ID: "lock.lock_1a2b",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "open_failed"


@pytest.mark.usefixtures("init_integration")
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


@pytest.mark.usefixtures("init_integration")
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


@pytest.mark.usefixtures("init_integration")
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


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("lib_state", "expected_state"),
    [
        (TedeeLockState.LOCKED, LockState.LOCKED),
        (TedeeLockState.HALF_OPEN, STATE_UNKNOWN),
        (TedeeLockState.UNKNOWN, STATE_UNKNOWN),
        (TedeeLockState.UNCALIBRATED, STATE_UNAVAILABLE),
    ],
)
async def test_webhook_update(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    hass_client_no_auth: ClientSessionGenerator,
    lib_state: TedeeLockState,
    expected_state: str,
) -> None:
    """Test updated data set through webhook."""

    state = hass.states.get("lock.lock_1a2b")
    assert state
    assert state.state == LockState.UNLOCKED

    webhook_data = {"dummystate": lib_state.value}
    # is updated in the lib, so mock and assert below
    mock_tedee.locks_dict[12345].state = lib_state
    client = await hass_client_no_auth()
    webhook_url = async_generate_url(hass, WEBHOOK_ID)

    await client.post(
        urlparse(webhook_url).path,
        json=webhook_data,
    )
    mock_tedee.parse_webhook_message.assert_called_once_with(webhook_data)

    state = hass.states.get("lock.lock_1a2b")
    assert state
    assert state.state == expected_state
