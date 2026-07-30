"""Tests for the IntesisHome climate platform."""

from unittest.mock import MagicMock, patch

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_PLATFORM, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_setup_platform_registers_callback(hass: HomeAssistant) -> None:
    """Test registering the synchronous library update callback during setup."""
    with patch(
        "homeassistant.components.intesishome.climate.IntesisHome", autospec=True
    ) as intesis_home:
        controller = intesis_home.return_value
        controller.device_type = "IntesisHome"
        controller.get_devices.return_value = {"device-id": {"name": "Office"}}
        controller.has_setpoint_control.return_value = False
        controller.has_vertical_swing.return_value = False
        controller.has_horizontal_swing.return_value = False
        controller.get_fan_speed_list.return_value = []
        controller.get_mode_list.return_value = []
        controller.add_update_callback = MagicMock()
        controller.is_connected = True
        controller.get_temperature.return_value = 22
        controller.get_fan_speed.return_value = None
        controller.is_on.return_value = False
        controller.get_min_setpoint.return_value = 16
        controller.get_max_setpoint.return_value = 30
        controller.get_rssi.return_value = None
        controller.get_run_hours.return_value = None
        controller.get_setpoint.return_value = 21
        controller.get_outdoor_temperature.return_value = None
        controller.get_mode.return_value = "cool"
        controller.get_preset_mode.return_value = None
        controller.get_vertical_swing.return_value = "auto/stop"
        controller.get_horizontal_swing.return_value = "auto/stop"
        controller.get_heat_power_consumption.return_value = None
        controller.get_cool_power_consumption.return_value = None

        assert await async_setup_component(
            hass,
            CLIMATE_DOMAIN,
            {
                CLIMATE_DOMAIN: {
                    CONF_PLATFORM: "intesishome",
                    CONF_USERNAME: "user",
                    CONF_PASSWORD: "password",
                }
            },
        )
        await hass.async_block_till_done()

    assert hass.states.get("climate.office") is not None
    controller.add_update_callback.assert_called_once()
    assert callable(controller.add_update_callback.call_args.args[0])
    controller.connect.assert_awaited_once_with()
