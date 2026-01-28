"""Tests for Vera energy sensors."""

from unittest.mock import MagicMock

import pyvera as pv

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant

from .common import ComponentFactory, new_simple_controller_config


async def test_switch_with_power_sensor(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test that a switch with power creates a power sensor."""
    vera_device: pv.VeraSwitch = MagicMock(spec=pv.VeraSwitch)
    vera_device.device_id = 1
    vera_device.vera_device_id = vera_device.device_id
    vera_device.comm_failure = False
    vera_device.name = "power_switch"
    vera_device.category = pv.CATEGORY_SWITCH
    vera_device.is_switched_on = MagicMock(return_value=True)
    vera_device.power = 50.5  # 50.5W
    vera_device.energy = None  # No energy tracking
    switch_entity_id = "switch.power_switch_1"
    power_entity_id = "sensor.power_switch_1_power"

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )

    # Verify switch entity exists
    assert hass.states.get(switch_entity_id).state == "on"

    # Verify power sensor was created
    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "50.5"
    assert power_state.attributes["device_class"] == SensorDeviceClass.POWER
    assert power_state.attributes["unit_of_measurement"] == UnitOfPower.WATT
    assert power_state.attributes["state_class"] == SensorStateClass.MEASUREMENT


async def test_switch_with_energy_sensor(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test that a switch with energy creates an energy sensor."""
    vera_device: pv.VeraSwitch = MagicMock(spec=pv.VeraSwitch)
    vera_device.device_id = 2
    vera_device.vera_device_id = vera_device.device_id
    vera_device.comm_failure = False
    vera_device.name = "energy_switch"
    vera_device.category = pv.CATEGORY_SWITCH
    vera_device.is_switched_on = MagicMock(return_value=True)
    vera_device.power = None  # No power tracking
    vera_device.energy = 12.345  # 12.345 kWh
    switch_entity_id = "switch.energy_switch_2"
    energy_entity_id = "sensor.energy_switch_2_energy"

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )

    # Verify switch entity exists
    assert hass.states.get(switch_entity_id).state == "on"

    # Verify energy sensor was created
    energy_state = hass.states.get(energy_entity_id)
    assert energy_state is not None
    assert energy_state.state == "12.345"
    assert energy_state.attributes["device_class"] == SensorDeviceClass.ENERGY
    assert energy_state.attributes["unit_of_measurement"] == UnitOfEnergy.KILO_WATT_HOUR
    assert energy_state.attributes["state_class"] == SensorStateClass.TOTAL_INCREASING


async def test_light_with_power_and_energy(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test that a light with both power and energy creates both sensors."""
    vera_device: pv.VeraDimmer = MagicMock(spec=pv.VeraDimmer)
    vera_device.device_id = 3
    vera_device.vera_device_id = vera_device.device_id
    vera_device.comm_failure = False
    vera_device.name = "smart_light"
    vera_device.category = pv.CATEGORY_DIMMER
    vera_device.is_switched_on = MagicMock(return_value=True)
    vera_device.get_brightness = MagicMock(return_value=75)
    vera_device.get_color = MagicMock(return_value=[0, 0, 0])
    vera_device.is_dimmable = True
    vera_device.power = 15.2  # 15.2W
    vera_device.energy = 5.67  # 5.67 kWh
    light_entity_id = "light.smart_light_3"
    power_entity_id = "sensor.smart_light_3_power"
    energy_entity_id = "sensor.smart_light_3_energy"

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )

    # Verify light entity exists
    assert hass.states.get(light_entity_id).state == "on"

    # Verify power sensor was created
    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "15.2"
    assert power_state.attributes["device_class"] == SensorDeviceClass.POWER

    # Verify energy sensor was created
    energy_state = hass.states.get(energy_entity_id)
    assert energy_state is not None
    assert energy_state.state == "5.67"
    assert energy_state.attributes["device_class"] == SensorDeviceClass.ENERGY


async def test_switch_without_power_no_sensor(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test that a switch without power does not create power/energy sensors."""
    vera_device: pv.VeraSwitch = MagicMock(spec=pv.VeraSwitch)
    vera_device.device_id = 4
    vera_device.vera_device_id = vera_device.device_id
    vera_device.comm_failure = False
    vera_device.name = "simple_switch"
    vera_device.category = pv.CATEGORY_SWITCH
    vera_device.is_switched_on = MagicMock(return_value=True)
    vera_device.power = None
    vera_device.energy = None
    switch_entity_id = "switch.simple_switch_4"
    power_entity_id = "sensor.simple_switch_4_power"
    energy_entity_id = "sensor.simple_switch_4_energy"

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )

    # Verify switch entity exists
    assert hass.states.get(switch_entity_id).state == "on"

    # Verify no power or energy sensors were created
    assert hass.states.get(power_entity_id) is None
    assert hass.states.get(energy_entity_id) is None
