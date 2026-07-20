"""Tests for the IntesisHome climate platform."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.intesishome.climate import IntesisAC


async def test_async_added_to_hass_registers_callback() -> None:
    """Test registering the synchronous library update callback."""
    controller = MagicMock()
    controller.device_type = "IntesisHome"
    controller.has_setpoint_control.return_value = False
    controller.has_vertical_swing.return_value = False
    controller.has_horizontal_swing.return_value = False
    controller.get_fan_speed_list.return_value = []
    controller.get_mode_list.return_value = []
    controller.add_update_callback = MagicMock()
    controller.connect = AsyncMock()

    entity = IntesisAC("device-id", {"name": "Office"}, controller)

    await entity.async_added_to_hass()

    controller.add_update_callback.assert_called_once_with(entity.async_update_callback)
    controller.connect.assert_awaited_once_with()
