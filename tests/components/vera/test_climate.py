"""Vera tests."""

from unittest.mock import MagicMock

import pytest
import pyvera as pv

from homeassistant.components.climate import FAN_AUTO, FAN_ON, HVACAction, HVACMode
from homeassistant.core import HomeAssistant

from .common import ComponentFactory, new_simple_controller_config


async def test_climate(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device: pv.VeraThermostat = MagicMock(spec=pv.VeraThermostat)
    vera_device.device_id = 1
    vera_device.vera_device_id = vera_device.device_id
    vera_device.comm_failure = False
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

    assert hass.states.get(entity_id).state == HVACMode.OFF

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVACMode.COOL},
    )
    await hass.async_block_till_done()
    vera_device.turn_cool_on.assert_called()
    vera_device.get_hvac_mode.return_value = "CoolOn"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == HVACMode.COOL

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVACMode.HEAT},
    )
    await hass.async_block_till_done()
    vera_device.turn_heat_on.assert_called()
    vera_device.get_hvac_mode.return_value = "HeatOn"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == HVACMode.HEAT

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVACMode.HEAT_COOL},
    )
    await hass.async_block_till_done()
    vera_device.turn_auto_on.assert_called()
    vera_device.get_hvac_mode.return_value = "AutoChangeOver"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == HVACMode.HEAT_COOL

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": entity_id, "hvac_mode": HVACMode.OFF},
    )
    await hass.async_block_till_done()
    vera_device.turn_auto_on.assert_called()
    vera_device.get_hvac_mode.return_value = "Off"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == HVACMode.OFF

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


@pytest.mark.parametrize(
    ("vera_hvac_state", "expected_hvac_action"),
    [
        pytest.param("Heating", HVACAction.HEATING, id="heating"),
        pytest.param("Cooling", HVACAction.COOLING, id="cooling"),
        pytest.param("PendingCool", HVACAction.COOLING, id="pending-cool"),
        pytest.param("PendingHeat", HVACAction.PREHEATING, id="pending-heat"),
        pytest.param("PendingIdle", HVACAction.IDLE, id="pending-idle"),
        pytest.param("Idle", HVACAction.IDLE, id="idle"),
        pytest.param("FanOnly", HVACAction.FAN, id="fan-only"),
        pytest.param("Vent", HVACAction.FAN, id="vent"),
        pytest.param("Off", HVACAction.OFF, id="off"),
        pytest.param("Unknown", None, id="unmapped"),
    ],
)
async def test_hvac_action(
    hass: HomeAssistant,
    vera_component_factory: ComponentFactory,
    vera_hvac_state: str,
    expected_hvac_action: HVACAction | None,
) -> None:
    """Test HVAC action."""
    vera_device: pv.VeraThermostat = MagicMock(spec=pv.VeraThermostat)
    vera_device.device_id = 1
    vera_device.vera_device_id = vera_device.device_id
    vera_device.comm_failure = False
    vera_device.name = "dev1"
    vera_device.category = pv.CATEGORY_THERMOSTAT
    vera_device.power = 10
    vera_device.get_current_temperature.return_value = 71
    vera_device.get_hvac_mode.return_value = "Off"
    vera_device.get_hvac_state.return_value = vera_hvac_state
    vera_device.get_current_goal_temperature.return_value = 72

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )

    state = hass.states.get("climate.dev1_1")
    assert state is not None
    assert state.attributes.get("hvac_action") == expected_hvac_action


async def test_climate_f(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device: pv.VeraThermostat = MagicMock(spec=pv.VeraThermostat)
    vera_device.device_id = 1
    vera_device.vera_device_id = vera_device.device_id
    vera_device.comm_failure = False
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
