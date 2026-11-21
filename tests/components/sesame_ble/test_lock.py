"""Tests for the Sesame BLE lock platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.sesame_ble.const import (
    CONF_DEVICE_UUID,
    CONF_SECRET_KEY,
    DOMAIN,
)
from homeassistant.components.sesame_ble.lock import PARALLEL_UPDATES, SesameBLELock
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

TEST_MAC = "AA:BB:CC:DD:EE:FF"
TEST_UUID = "01234567-89ab-cdef-0123-456789abcdef"


def _build_mock_wrapper(
    *,
    is_locked: bool | None = True,
    is_logged_in: bool = True,
) -> MagicMock:
    """Build a mock SesameDeviceWrapper for testing."""
    sesame_mock = MagicMock()
    sesame_mock.is_locked = is_locked
    sesame_mock.is_logged_in = is_logged_in
    sesame_mock.is_moving = False
    sesame_mock.current_angle = 120
    sesame_mock.target_angle = 120
    sesame_mock.lock_position = 120
    sesame_mock.unlock_position = 0
    sesame_mock.lock = AsyncMock()
    sesame_mock.unlock = AsyncMock()

    ble_dev = MagicMock()
    ble_dev.address = TEST_MAC

    entry_mock = MagicMock()
    entry_mock.unique_id = "test_lock_entry"
    entry_mock.title = "Sesame 5 (EE:FF)"

    wrapper = MagicMock()
    wrapper.device = sesame_mock
    wrapper.ble_device = ble_dev
    wrapper.entry = entry_mock
    wrapper.mac_address = TEST_MAC
    wrapper.model_name = "SESAME5"
    wrapper.available = True
    wrapper.register_update_listener = MagicMock()
    wrapper.async_connect = AsyncMock()

    return wrapper


async def test_lock_setup_and_properties(hass: HomeAssistant) -> None:
    """Test lock entity properties and registration."""
    wrapper = _build_mock_wrapper()
    lock = SesameBLELock(wrapper)

    assert PARALLEL_UPDATES == 1
    assert lock.has_entity_name is True
    assert lock.should_poll is False
    assert lock.unique_id == "test_lock_entry"
    assert lock.name is None
    assert lock.available is True
    assert lock.is_locked is True
    assert lock.is_locking is False
    assert lock.is_unlocking is False

    device_info = lock.device_info
    assert device_info["identifiers"] == {(DOMAIN, "test_lock_entry")}
    assert device_info["name"] == "Sesame 5 (EE:FF)"
    assert device_info["manufacturer"] == "CANDY HOUSE"
    assert device_info["model"] == "5"


async def test_lock_is_locking_and_unlocking() -> None:
    """Test is_locking and is_unlocking state properties."""
    wrapper = _build_mock_wrapper()
    wrapper.device.is_moving = True
    wrapper.device.lock_position = 120
    wrapper.device.unlock_position = 0

    # Moving towards locked
    wrapper.device.target_angle = 120
    lock = SesameBLELock(wrapper)
    assert lock.is_locking is True
    assert lock.is_unlocking is False

    # Moving towards unlocked
    wrapper.device.target_angle = 0
    assert lock.is_locking is False
    assert lock.is_unlocking is True


async def test_lock_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup registers the lock entity."""
    mock_ble_device = MagicMock()
    mock_ble_device.address = TEST_MAC
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Sesame 5",
        data={
            "mac_address": TEST_MAC,
            CONF_SECRET_KEY: "0123456789abcdef0123456789abcdef",
            CONF_MODEL: "SESAME5",
            CONF_DEVICE_UUID: TEST_UUID,
        },
        unique_id="entry_unique_id",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_ble_device_from_address",
            return_value=mock_ble_device,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_last_service_info",
            return_value=None,
        ),
        patch(
            "homeassistant.components.sesame_ble.bluetooth.async_register_callback",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.sesame_ble.SesameDeviceWrapper.async_connect",
            new_callable=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get("lock.sesame_5")
    assert state is not None


async def test_lock_lifecycle_and_listener(hass: HomeAssistant) -> None:
    """Test listener registration on add and cleanup on removal."""
    wrapper = _build_mock_wrapper()
    unregister_cb = MagicMock()
    wrapper.register_update_listener.return_value = unregister_cb

    lock = SesameBLELock(wrapper)
    lock.hass = hass

    await lock.async_added_to_hass()
    wrapper.register_update_listener.assert_called_once()

    await lock.async_will_remove_from_hass()
    unregister_cb.assert_called_once()


async def test_lock_action_success() -> None:
    """Test successful async_lock call."""
    wrapper = _build_mock_wrapper()
    lock = SesameBLELock(wrapper)

    await lock.async_lock()
    wrapper.device.lock.assert_awaited_once_with(history_name="Home Assistant")


async def test_lock_action_failure_raises_ha_error() -> None:
    """Test async_lock raises HomeAssistantError on underlying failure."""
    wrapper = _build_mock_wrapper()
    wrapper.device.lock.side_effect = RuntimeError("Bluetooth transmission timeout")

    lock = SesameBLELock(wrapper)

    with pytest.raises(HomeAssistantError) as exc_info:
        await lock.async_lock()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "lock_failed"


async def test_unlock_action_success() -> None:
    """Test successful async_unlock call."""
    wrapper = _build_mock_wrapper()
    lock = SesameBLELock(wrapper)

    await lock.async_unlock()
    wrapper.device.unlock.assert_awaited_once_with(history_name="Home Assistant")


async def test_unlock_action_failure_raises_ha_error() -> None:
    """Test async_unlock raises HomeAssistantError on underlying failure."""
    wrapper = _build_mock_wrapper()
    wrapper.device.unlock.side_effect = RuntimeError("Device disconnected")

    lock = SesameBLELock(wrapper)

    with pytest.raises(HomeAssistantError) as exc_info:
        await lock.async_unlock()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "unlock_failed"


async def test_lock_action_reconnects_when_not_logged_in() -> None:
    """Test async_lock reconnects when device is not logged in."""
    wrapper = _build_mock_wrapper(is_logged_in=False)
    lock = SesameBLELock(wrapper)

    await lock.async_lock()
    wrapper.async_connect.assert_awaited_once()
    wrapper.device.lock.assert_awaited_once_with(history_name="Home Assistant")


async def test_unlock_action_reconnects_when_not_logged_in() -> None:
    """Test async_unlock reconnects when device is not logged in."""
    wrapper = _build_mock_wrapper(is_logged_in=False)
    lock = SesameBLELock(wrapper)

    await lock.async_unlock()
    wrapper.async_connect.assert_awaited_once()
    wrapper.device.unlock.assert_awaited_once_with(history_name="Home Assistant")
