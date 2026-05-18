"""Test schlage switch."""

from collections.abc import Awaitable, Callable
from unittest.mock import Mock

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockSchlageConfigEntry

from tests.common import SnapshotAssertion, patch, snapshot_platform


async def test_switch_attributes(
    hass: HomeAssistant,
    mock_add_config_entry: Callable[[], Awaitable[MockSchlageConfigEntry]],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switch attributes."""
    with patch("homeassistant.components.schlage.PLATFORMS", [Platform.SWITCH]):
        config_entry = await mock_add_config_entry()
        await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_beeper_services(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test BeeperSwitch services."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        service_data={ATTR_ENTITY_ID: "switch.vault_door_keypress_beep"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_lock.set_beeper.assert_called_once_with(False)
    mock_lock.set_beeper.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "switch.vault_door_keypress_beep"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_lock.set_beeper.assert_called_once_with(True)

    await hass.config_entries.async_unload(mock_added_config_entry.entry_id)


async def test_lock_and_leave_services(
    hass: HomeAssistant,
    mock_lock: Mock,
    mock_added_config_entry: MockSchlageConfigEntry,
) -> None:
    """Test LockAndLeaveSwitch services."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        service_data={ATTR_ENTITY_ID: "switch.vault_door_1_touch_locking"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_lock.set_lock_and_leave.assert_called_once_with(False)
    mock_lock.set_lock_and_leave.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: "switch.vault_door_1_touch_locking"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_lock.set_lock_and_leave.assert_called_once_with(True)

    await hass.config_entries.async_unload(mock_added_config_entry.entry_id)
