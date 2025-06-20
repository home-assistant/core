"""Test the switchbot switches."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest
from switchbot.devices.device import SwitchbotOperationError

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError

from . import WOHAND_SERVICE_INFO

from tests.common import MockConfigEntry, mock_restore_cache
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_switchbot_switch_with_restore_state(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test that Switchbot Switch restores state correctly after reboot."""
    inject_bluetooth_service_info(hass, WOHAND_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="bot")
    entity_id = "switch.test_name"

    mock_restore_cache(
        hass,
        [
            State(
                entity_id,
                STATE_ON,
                {"last_run_success": True},
            )
        ],
    )

    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.switchbot.switch.switchbot.Switchbot.switch_mode",
        return_value=False,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON
        assert state.attributes["last_run_success"] is True


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
        (SERVICE_TURN_ON, "turn_on"),
        (SERVICE_TURN_OFF, "turn_off"),
    ],
)
async def test_exception_handling_switch(
    hass: HomeAssistant,
    mock_entry_factory: Callable[[str], MockConfigEntry],
    service: str,
    mock_method: str,
    exception: Exception,
    error_message: str,
) -> None:
    """Test exception handling for switch service with exception."""
    inject_bluetooth_service_info(hass, WOHAND_SERVICE_INFO)

    entry = mock_entry_factory(sensor_type="bot")
    entry.add_to_hass(hass)
    entity_id = "switch.test_name"

    patch_target = (
        f"homeassistant.components.switchbot.switch.switchbot.Switchbot.{mock_method}"
    )

    with patch(patch_target, new=AsyncMock(side_effect=exception)):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match=error_message):
            await hass.services.async_call(
                SWITCH_DOMAIN,
                service,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
