"""Test the switchbot locks."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.components.switchbot.const import (
    CONF_ENCRYPTION_KEY,
    CONF_KEY_ID,
    DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_SENSOR_TYPE,
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import WOLOCK_SERVICE_INFO, WOLOCKPRO_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_lockpro_lock_and_unlock(hass: HomeAssistant) -> None:
    """Test lock and unlock on lockpro."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOLOCKPRO_SERVICE_INFO)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "lock_pro",
            CONF_KEY_ID: "ff",
            CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "switchbot.SwitchbotLock.lock", new=AsyncMock(return_value=True)
        ) as mock_lock,
        patch(
            "switchbot.SwitchbotLock.unlock", new=AsyncMock(return_value=True)
        ) as mock_unlock,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        entity_id = "lock.test_name"
        assert hass.states.get(entity_id).state == LockState.LOCKED

        # Test Unlock
        await hass.services.async_call(
            LOCK_DOMAIN, SERVICE_UNLOCK, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_unlock.assert_awaited_once()
        assert hass.states.get(entity_id).state == LockState.UNLOCKED

        # Test Lock
        await hass.services.async_call(
            LOCK_DOMAIN, SERVICE_LOCK, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_lock.assert_awaited_once()
        assert hass.states.get(entity_id).state == LockState.LOCKED


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_lock_open(hass: HomeAssistant) -> None:
    """Test open on lock."""
    await async_setup_component(hass, DOMAIN, {})
    inject_bluetooth_service_info(hass, WOLOCK_SERVICE_INFO)
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_ADDRESS: "aa:bb:cc:dd:ee:ff",
            CONF_NAME: "test-name",
            CONF_SENSOR_TYPE: "lock",
            CONF_KEY_ID: "ff",
            CONF_ENCRYPTION_KEY: "ffffffffffffffffffffffffffffffff",
        },
        unique_id="aabbccddeeff",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "switchbot.SwitchbotLock.is_night_latch_enabled",
            new=MagicMock(return_value=True),
        ) as mock_is_night_latch_enabled,
        patch(
            "switchbot.SwitchbotLock.unlock_without_unlatch",
            new=AsyncMock(return_value=True),
        ) as mock_unlock_without_unlatch,
        patch(
            "switchbot.SwitchbotLock.unlock", new=AsyncMock(return_value=True)
        ) as mock_unlock,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_is_night_latch_enabled.assert_called_once()

        entity_id = "lock.test_name"
        assert hass.states.get(entity_id).state == LockState.LOCKED

        # Test unlock_without_unlatch
        await hass.services.async_call(
            LOCK_DOMAIN, SERVICE_UNLOCK, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_unlock_without_unlatch.assert_awaited_once()
        assert hass.states.get(entity_id).state == LockState.UNLOCKED

        # Test open
        await hass.services.async_call(
            LOCK_DOMAIN, SERVICE_OPEN, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
        mock_unlock.assert_awaited_once()
        assert hass.states.get(entity_id).state == LockState.OPEN
