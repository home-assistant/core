"""Test the switchbot switches."""

from collections.abc import Callable
from unittest.mock import AsyncMock, patch

import pytest
from switchbot import SwitchbotOperationError

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import GARAGE_DOOR_OPENER_SERVICE_INFO

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_button_press(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test that Switchbot Button press works."""
    inject_bluetooth_service_info(hass, GARAGE_DOOR_OPENER_SERVICE_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="garage_door_opener")
    entry.add_to_hass(hass)
    entity_id = "button.test_name"

    with patch.multiple(
        "homeassistant.components.switchbot.button.switchbot.SwitchbotGarageDoorOpener",
        update=AsyncMock(),
        press=AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


async def test_button_press_exception(
    hass: HomeAssistant,
    mock_entry_encrypted_factory: Callable[[str], MockConfigEntry],
) -> None:
    """Test that Switchbot Button press raises an exception."""
    inject_bluetooth_service_info(hass, GARAGE_DOOR_OPENER_SERVICE_INFO)

    entry = mock_entry_encrypted_factory(sensor_type="garage_door_opener")
    entry.add_to_hass(hass)
    entity_id = "button.test_name"

    error_message = "An error occurred while performing the action: Test error"
    with patch.multiple(
        "homeassistant.components.switchbot.button.switchbot.SwitchbotGarageDoorOpener",
        update=AsyncMock(),
        press=AsyncMock(side_effect=SwitchbotOperationError("Test error")),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError, match=error_message):
            await hass.services.async_call(
                BUTTON_DOMAIN,
                SERVICE_PRESS,
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
            )
