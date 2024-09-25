"""Test schlage lock."""

from datetime import timedelta
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockState
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_LOCK, SERVICE_UNLOCK
from homeassistant.core import HomeAssistant

from tests.common import async_fire_time_changed


async def test_lock_attributes(
    hass: HomeAssistant,
    mock_added_config_entry: ConfigEntry,
    mock_schlage: Mock,
    mock_lock: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test lock attributes."""
    lock = hass.states.get("lock.vault_door")
    assert lock is not None
    assert lock.state == LockState.UNLOCKED
    assert lock.attributes["changed_by"] == "thumbturn"

    mock_lock.is_locked = False
    mock_lock.is_jammed = True
    # Make the coordinator refresh data.
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    lock = hass.states.get("lock.vault_door")
    assert lock is not None
    assert lock.state == LockState.JAMMED


async def test_lock_services(
    hass: HomeAssistant, mock_lock: Mock, mock_added_config_entry: ConfigEntry
) -> None:
    """Test lock services."""
    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_LOCK,
        service_data={ATTR_ENTITY_ID: "lock.vault_door"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_lock.lock.assert_called_once_with()

    await hass.services.async_call(
        LOCK_DOMAIN,
        SERVICE_UNLOCK,
        service_data={ATTR_ENTITY_ID: "lock.vault_door"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_lock.unlock.assert_called_once_with()

    await hass.config_entries.async_unload(mock_added_config_entry.entry_id)


async def test_changed_by(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: ConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test population of the changed_by attribute."""
    mock_lock.last_changed_by.reset_mock()
    mock_lock.last_changed_by.return_value = "access code - foo"

    # Make the coordinator refresh data.
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_lock.last_changed_by.assert_called_with()

    lock_device = hass.states.get("lock.vault_door")
    assert lock_device is not None
    assert lock_device.attributes.get("changed_by") == "access code - foo"
