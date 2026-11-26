"""Test schlage switch."""

from collections.abc import Awaitable, Callable
from unittest.mock import Mock, patch

from pyschlage.exceptions import Error as SchlageError
import pytest
from pytest_homeassistant.common import snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN, SwitchService
from homeassistant.const import Platform, TargetKey
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import MockSchlageConfigEntry


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
        SwitchService.TURN_OFF,
        service_data={TargetKey.ENTITY_ID: "switch.vault_door_keypress_beep"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_lock.set_beeper.assert_called_once_with(False)
    mock_lock.set_beeper.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_ON,
        service_data={TargetKey.ENTITY_ID: "switch.vault_door_keypress_beep"},
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
        SwitchService.TURN_OFF,
        service_data={TargetKey.ENTITY_ID: "switch.vault_door_1_touch_locking"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_lock.set_lock_and_leave.assert_called_once_with(False)
    mock_lock.set_lock_and_leave.reset_mock()

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SwitchService.TURN_ON,
        service_data={TargetKey.ENTITY_ID: "switch.vault_door_1_touch_locking"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_lock.set_lock_and_leave.assert_called_once_with(True)

    await hass.config_entries.async_unload(mock_added_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        pytest.param("switch.vault_door_keypress_beep", "set_beeper", id="beeper"),
        pytest.param(
            "switch.vault_door_1_touch_locking",
            "set_lock_and_leave",
            id="lock_and_leave",
        ),
    ],
)
@pytest.mark.parametrize("service", [SwitchService.TURN_ON, SwitchService.TURN_OFF])
@pytest.mark.usefixtures("mock_added_config_entry")
async def test_switch_services_api_error(
    hass: HomeAssistant,
    mock_lock: Mock,
    entity_id: str,
    method: str,
    service: SwitchService,
) -> None:
    """Test switch services raise HomeAssistantError on API failure."""
    getattr(mock_lock, method).side_effect = SchlageError("API error")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            service,
            service_data={TargetKey.ENTITY_ID: entity_id},
            blocking=True,
        )
    assert exc_info.value.translation_key == "schlage_command_failed"
