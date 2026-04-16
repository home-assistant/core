"""Test the switchbot locks."""

from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from switchbot import LockStatus, SwitchbotOperationError

from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.components.switchbot.const import DOMAIN
from homeassistant.const import (
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr

from . import (
    LOCK_LITE_SERVICE_INFO,
    LOCK_SERVICE_INFO,
    LOCK_ULTRA_SERVICE_INFO,
    WOLOCKPRO_SERVICE_INFO,
)

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.parametrize(
    ("sensor_type", "service_info"),
    [
        ("lock_pro", WOLOCKPRO_SERVICE_INFO),
        ("lock", LOCK_SERVICE_INFO),
        ("lock_lite", LOCK_LITE_SERVICE_INFO),
        ("lock_ultra", LOCK_ULTRA_SERVICE_INFO),
    ],
)
@pytest.mark.parametrize(
    ("service", "mock_method"),
    [(SERVICE_UNLOCK, "unlock"), (SERVICE_LOCK, "lock")],
)
async def test_lock_services(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    sensor_type: str,
    service: str,
    mock_method: str,
    service_info: BluetoothServiceInfoBleak,
) -> None:
    """Test lock and unlock services on lock and lockpro devices."""
    inject_bluetooth_service_info(hass, service_info)

    entry = mock_entry_encrypted_factory(sensor_type=sensor_type)
    entry.add_to_hass(hass)
    mocked_instance = AsyncMock(return_value=True)

    with patch.multiple(
        "homeassistant.components.switchbot.lock.switchbot.SwitchbotLock",
        update=AsyncMock(return_value=None),
        **{mock_method: mocked_instance},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "lock.test_name"

        await hass.services.async_call(
            LOCK_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mocked_instance.assert_awaited_once()


@pytest.mark.parametrize(
    ("sensor_type", "service_info"),
    [
        ("lock_pro", WOLOCKPRO_SERVICE_INFO),
        ("lock", LOCK_SERVICE_INFO),
        ("lock_lite", LOCK_LITE_SERVICE_INFO),
        ("lock_ultra", LOCK_ULTRA_SERVICE_INFO),
    ],
)
@pytest.mark.parametrize(
    ("service", "mock_method"),
    [(SERVICE_UNLOCK, "unlock_without_unlatch"), (SERVICE_OPEN, "unlock")],
)
async def test_lock_services_with_night_latch_enabled(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    sensor_type: str,
    service: str,
    mock_method: str,
    service_info: BluetoothServiceInfoBleak,
) -> None:
    """Test lock service when night latch enabled."""
    inject_bluetooth_service_info(hass, service_info)

    entry = mock_entry_encrypted_factory(sensor_type=sensor_type)
    entry.add_to_hass(hass)
    mocked_instance = AsyncMock(return_value=True)

    with patch.multiple(
        "homeassistant.components.switchbot.lock.switchbot.SwitchbotLock",
        is_night_latch_enabled=MagicMock(return_value=True),
        update=AsyncMock(return_value=None),
        **{mock_method: mocked_instance},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "lock.test_name"

        await hass.services.async_call(
            LOCK_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        mocked_instance.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "error_message"),
    [
        (
            SwitchbotOperationError("Operation failed"),
            "An error occurred while performing the action: Operation failed",
        ),
    ],
)
@pytest.mark.parametrize(
    ("service", "mock_method"),
    [
        (SERVICE_LOCK, "lock"),
        (SERVICE_OPEN, "unlock"),
        (SERVICE_UNLOCK, "unlock_without_unlatch"),
    ],
)
async def test_exception_handling_lock_service(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
    service: str,
    mock_method: str,
    exception: Exception,
    error_message: str,
) -> None:
    """Test exception handling for lock service with exception."""
    inject_bluetooth_service_info(hass, LOCK_SERVICE_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="lock")
    entry.add_to_hass(hass)
    entity_id = "lock.test_name"

    with patch.multiple(
        "homeassistant.components.switchbot.lock.switchbot.SwitchbotLock",
        is_night_latch_enabled=MagicMock(return_value=True),
        update=AsyncMock(return_value=None),
        **{mock_method: AsyncMock(side_effect=exception)},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match=error_message):
            await hass.services.async_call(
                LOCK_DOMAIN,
                service,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )


async def test_lock_ultra_half_lock_service(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test half_lock service calls half_lock() on Lock Ultra."""
    inject_bluetooth_service_info(hass, LOCK_ULTRA_SERVICE_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="lock_ultra")
    entry.add_to_hass(hass)
    mocked_half_lock = AsyncMock(return_value=True)

    with patch.multiple(
        "homeassistant.components.switchbot.lock.switchbot.SwitchbotLock",
        update=AsyncMock(return_value=None),
        is_night_latch_enabled=MagicMock(return_value=True),
        half_lock=mocked_half_lock,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        device_registry = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        device_id = devices[0].id

        await hass.services.async_call(
            DOMAIN,
            "half_lock",
            {ATTR_DEVICE_ID: device_id},
            blocking=True,
        )

        mocked_half_lock.assert_awaited_once()


async def test_lock_ultra_half_lock_service_wrong_device(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test half_lock service raises error for non-Lock-Ultra devices."""
    inject_bluetooth_service_info(hass, LOCK_SERVICE_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="lock")
    entry.add_to_hass(hass)

    with patch.multiple(
        "homeassistant.components.switchbot.lock.switchbot.SwitchbotLock",
        update=AsyncMock(return_value=None),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        device_registry = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        device_id = devices[0].id

        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN,
                "half_lock",
                {ATTR_DEVICE_ID: device_id},
                blocking=True,
            )


async def test_lock_ultra_half_lock_state_shows_locked(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test that Lock Ultra in HALF_LOCKED state shows as locked in HA UI."""
    inject_bluetooth_service_info(hass, LOCK_ULTRA_SERVICE_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="lock_ultra")
    entry.add_to_hass(hass)

    with patch.multiple(
        "homeassistant.components.switchbot.lock.switchbot.SwitchbotLock",
        update=AsyncMock(return_value=None),
        get_lock_status=MagicMock(return_value=LockStatus.HALF_LOCKED),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        lock_state = hass.states.get("lock.test_name")
        assert lock_state is not None
        assert lock_state.state == LockState.LOCKED
        assert lock_state.attributes["half_locked"] is True


async def test_lock_ultra_half_locked_state(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test half_locked extra state attribute is True when status is HALF_LOCKED."""
    inject_bluetooth_service_info(hass, LOCK_ULTRA_SERVICE_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="lock_ultra")
    entry.add_to_hass(hass)

    with patch.multiple(
        "homeassistant.components.switchbot.lock.switchbot.SwitchbotLock",
        update=AsyncMock(return_value=None),
        get_lock_status=MagicMock(return_value=LockStatus.HALF_LOCKED),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        lock_state = hass.states.get("lock.test_name")
        assert lock_state is not None
        assert lock_state.attributes["half_locked"] is True


async def test_non_lock_ultra_no_half_locked_attr(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test half_locked attribute is absent for non-Lock-Ultra devices."""
    inject_bluetooth_service_info(hass, LOCK_SERVICE_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="lock")
    entry.add_to_hass(hass)

    with patch.multiple(
        "homeassistant.components.switchbot.lock.switchbot.SwitchbotLock",
        update=AsyncMock(return_value=None),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        lock_state = hass.states.get("lock.test_name")
        assert lock_state is not None
        assert "half_locked" not in lock_state.attributes


async def test_lock_ultra_half_lock_service_not_calibrated(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test half_lock service raises HomeAssistantError when not calibrated."""
    inject_bluetooth_service_info(hass, LOCK_ULTRA_SERVICE_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="lock_ultra")
    entry.add_to_hass(hass)

    with patch.multiple(
        "homeassistant.components.switchbot.lock.switchbot.SwitchbotLock",
        update=AsyncMock(return_value=None),
        is_night_latch_enabled=MagicMock(return_value=True),
        half_lock=AsyncMock(
            side_effect=SwitchbotOperationError("Half lock is not calibrated")
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        device_registry = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        device_id = devices[0].id

        with pytest.raises(
            HomeAssistantError,
            match="An error occurred while performing the action: Half lock is not calibrated",
        ):
            await hass.services.async_call(
                DOMAIN,
                "half_lock",
                {ATTR_DEVICE_ID: device_id},
                blocking=True,
            )


async def test_lock_ultra_half_lock_service_not_eu(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test half_lock service raises ServiceValidationError for non-EU Lock Ultra."""
    inject_bluetooth_service_info(hass, LOCK_ULTRA_SERVICE_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="lock_ultra")
    entry.add_to_hass(hass)

    with patch.multiple(
        "homeassistant.components.switchbot.lock.switchbot.SwitchbotLock",
        update=AsyncMock(return_value=None),
        is_night_latch_enabled=MagicMock(return_value=False),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        device_registry = dr.async_get(hass)
        devices = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        device_id = devices[0].id

        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN,
                "half_lock",
                {ATTR_DEVICE_ID: device_id},
                blocking=True,
            )
