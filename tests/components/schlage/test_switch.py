"""Test schlage switch."""

from unittest.mock import Mock

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant

from . import MockSchlageConfigEntry


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
