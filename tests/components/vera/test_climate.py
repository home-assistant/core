"""Vera tests."""
import pyvera as pv

from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_ON,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_HEAT_COOL,
    HVAC_MODE_OFF,
)
from homeassistant.core import HomeAssistant

from .common import ComponentFactory, new_simple_controller_config

from tests.async_mock import MagicMock


async def test_climate(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device = MagicMock(spec=pv.VeraThermostat)  # type: pv.VeraThermostat
    vera_device.device_id = 1
    vera_device.vera_device_id = vera_device.device_id
    vera_device.name = "dev1"
    vera_device.category = pv.CATEGORY_THERMOSTAT
    vera_device.power = 10
    vera_device.get_current_temperature.return_value = 71
    vera_device.get_hvac_mode.return_value = "Off"
    vera_device.get_current_goal_temperature.return_value = 72
    entity_id = "climate.dev1_1"

    component_data = await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )
    update_callback = component_data.controller_data[0].update_callback

    assert hass.states.get(entity_id).state == HVAC_MODE_OFF

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVAC_MODE_COOL},
    )
    await hass.async_block_till_done()
    vera_device.turn_cool_on.assert_called()
    vera_device.get_hvac_mode.return_value = "CoolOn"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == HVAC_MODE_COOL

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVAC_MODE_HEAT},
    )
    await hass.async_block_till_done()
    vera_device.turn_heat_on.assert_called()
    vera_device.get_hvac_mode.return_value = "HeatOn"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == HVAC_MODE_HEAT

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVAC_MODE_HEAT_COOL},
    )
    await hass.async_block_till_done()
    vera_device.turn_auto_on.assert_called()
    vera_device.get_hvac_mode.return_value = "AutoChangeOver"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == HVAC_MODE_HEAT_COOL

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVAC_MODE_OFF},
    )
    await hass.async_block_till_done()
    vera_device.turn_auto_on.assert_called()
    vera_device.get_hvac_mode.return_value = "Off"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == HVAC_MODE_OFF

    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": entity_id, "fan_mode": "on"},
    )
    await hass.async_block_till_done()
    vera_device.turn_auto_on.assert_called()
    vera_device.get_fan_mode.return_value = "ContinuousOn"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["fan_mode"] == FAN_ON

    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": entity_id, "fan_mode": "off"},
    )
    await hass.async_block_till_done()
    vera_device.turn_auto_on.assert_called()
    vera_device.get_fan_mode.return_value = "Auto"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["fan_mode"] == FAN_AUTO

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": entity_id, "temperature": 30},
    )
    await hass.async_block_till_done()
    vera_device.set_temperature.assert_called_with(30)
    vera_device.get_current_goal_temperature.return_value = 30
    vera_device.get_current_temperature.return_value = 25
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["current_temperature"] == 25
    assert hass.states.get(entity_id).attributes["temperature"] == 30


async def test_climate_f(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device = MagicMock(spec=pv.VeraThermostat)  # type: pv.VeraThermostat
    vera_device.device_id = 1
    vera_device.vera_device_id = vera_device.device_id
    vera_device.name = "dev1"
    vera_device.category = pv.CATEGORY_THERMOSTAT
    vera_device.power = 10
    vera_device.get_current_temperature.return_value = 71
    vera_device.get_hvac_mode.return_value = "Off"
    vera_device.get_current_goal_temperature.return_value = 72
    entity_id = "climate.dev1_1"

    def setup_callback(controller: pv.VeraController) -> None:
        controller.temperature_units = "F"

    component_data = await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            devices=(vera_device,), setup_callback=setup_callback
        ),
    )
    update_callback = component_data.controller_data[0].update_callback

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": entity_id, "temperature": 30},
    )
    await hass.async_block_till_done()
    vera_device.set_temperature.assert_called_with(86)
    vera_device.get_current_goal_temperature.return_value = 30
    vera_device.get_current_temperature.return_value = 25
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["current_temperature"] == -3.9
    assert hass.states.get(entity_id).attributes["temperature"] == -1.1
