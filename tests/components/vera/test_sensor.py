"""Vera tests."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pyvera as pv

from homeassistant.components.sensor import async_rounded_state
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, LIGHT_LUX, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import ComponentFactory, new_simple_controller_config


async def run_sensor_test(
    hass: HomeAssistant,
    vera_component_factory: ComponentFactory,
    category: int,
    class_property: str,
    assert_states: tuple[tuple[Any, Any]],
    assert_unit_of_measurement: str | None = None,
    setup_callback: Callable[[pv.VeraController], None] | None = None,
) -> None:
    """Test generic sensor."""
    vera_device: pv.VeraSensor = MagicMock(spec=pv.VeraSensor)
    vera_device.device_id = 1
    vera_device.vera_device_id = vera_device.device_id
    vera_device.comm_failure = False
    vera_device.name = "dev1"
    vera_device.category = category
    setattr(vera_device, class_property, "33")
    entity_id = "sensor.dev1_1"

    component_data = await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            devices=(vera_device,), setup_callback=setup_callback
        ),
    )
    update_callback = component_data.controller_data[0].update_callback

    for initial_value, state_value in assert_states:
        setattr(vera_device, class_property, initial_value)
        update_callback(vera_device)
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert async_rounded_state(hass, entity_id, state) == state_value
        if assert_unit_of_measurement:
            assert (
                state.attributes[ATTR_UNIT_OF_MEASUREMENT] == assert_unit_of_measurement
            )


async def test_temperature_sensor_f(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""

    def setup_callback(controller: pv.VeraController) -> None:
        controller.temperature_units = "F"

    await run_sensor_test(
        hass=hass,
        vera_component_factory=vera_component_factory,
        category=pv.CATEGORY_TEMPERATURE_SENSOR,
        class_property="temperature",
        assert_states=(("33", "0.6"), ("44", "6.7")),
        setup_callback=setup_callback,
    )


async def test_temperature_sensor_c(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    await run_sensor_test(
        hass=hass,
        vera_component_factory=vera_component_factory,
        category=pv.CATEGORY_TEMPERATURE_SENSOR,
        class_property="temperature",
        assert_states=(("33", "33.0"), ("44", "44.0")),
    )


async def test_light_sensor(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    await run_sensor_test(
        hass=hass,
        vera_component_factory=vera_component_factory,
        category=pv.CATEGORY_LIGHT_SENSOR,
        class_property="light",
        assert_states=(("12", "12"), ("13", "13")),
        assert_unit_of_measurement=LIGHT_LUX,
    )


async def test_uv_sensor(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    await run_sensor_test(
        hass=hass,
        vera_component_factory=vera_component_factory,
        category=pv.CATEGORY_UV_SENSOR,
        class_property="light",
        assert_states=(("12", "12"), ("13", "13")),
        assert_unit_of_measurement="level",
    )


async def test_humidity_sensor(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    await run_sensor_test(
        hass=hass,
        vera_component_factory=vera_component_factory,
        category=pv.CATEGORY_HUMIDITY_SENSOR,
        class_property="humidity",
        assert_states=(("12", "12"), ("13", "13")),
        assert_unit_of_measurement=PERCENTAGE,
    )


async def test_power_meter_sensor(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    await run_sensor_test(
        hass=hass,
        vera_component_factory=vera_component_factory,
        category=pv.CATEGORY_POWER_METER,
        class_property="power",
        assert_states=(("12", "12"), ("13", "13")),
        assert_unit_of_measurement="W",
    )


async def test_trippable_sensor(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""

    def setup_callback(controller: pv.VeraController) -> None:
        controller.get_devices()[0].is_trippable = True

    await run_sensor_test(
        hass=hass,
        vera_component_factory=vera_component_factory,
        category=999,
        class_property="is_tripped",
        assert_states=((True, "Tripped"), (False, "Not Tripped"), (True, "Tripped")),
        setup_callback=setup_callback,
    )


async def test_unknown_sensor(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""

    def setup_callback(controller: pv.VeraController) -> None:
        controller.get_devices()[0].is_trippable = False

    await run_sensor_test(
        hass=hass,
        vera_component_factory=vera_component_factory,
        category=999,
        class_property="is_tripped",
        assert_states=((True, "Unknown"), (False, "Unknown"), (True, "Unknown")),
        setup_callback=setup_callback,
    )


async def test_scene_controller_sensor(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device: pv.VeraSensor = MagicMock(spec=pv.VeraSensor)
    vera_device.device_id = 1
    vera_device.vera_device_id = vera_device.device_id
    vera_device.comm_failure = False
    vera_device.name = "dev1"
    vera_device.category = pv.CATEGORY_SCENE_CONTROLLER
    vera_device.get_last_scene_id = MagicMock(return_value="id0")
    vera_device.get_last_scene_time = MagicMock(return_value="0000")
    entity_id = "sensor.dev1_1"

    component_data = await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )
    update_callback = component_data.controller_data[0].update_callback

    vera_device.get_last_scene_time.return_value = "1111"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "id0"


async def test_switch_power_and_energy_sensors_created(
    hass: HomeAssistant,
    vera_component_factory: ComponentFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that switches with metering expose power and energy sensors."""
    vera_switch: pv.VeraSwitch = MagicMock(spec=pv.VeraSwitch)
    vera_switch.device_id = 1
    vera_switch.vera_device_id = vera_switch.device_id
    vera_switch.comm_failure = False
    vera_switch.name = "metered_switch"
    vera_switch.category = 0
    vera_switch.power = 12
    vera_switch.energy = 3

    vera_sensor: pv.VeraSensor = MagicMock(spec=pv.VeraSensor)
    vera_sensor.device_id = 2
    vera_sensor.vera_device_id = vera_sensor.device_id
    vera_sensor.comm_failure = False
    vera_sensor.name = "dummy_sensor"
    vera_sensor.category = pv.CATEGORY_TEMPERATURE_SENSOR
    vera_sensor.temperature = "20"

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            devices=(vera_switch, vera_sensor)
        ),
    )
    await hass.async_block_till_done()

    power_entity_id = entity_registry.async_get_entity_id(
        "sensor", "vera", "vera_1111_1_power"
    )
    energy_entity_id = entity_registry.async_get_entity_id(
        "sensor", "vera", "vera_1111_1_energy"
    )

    assert power_entity_id is not None
    assert energy_entity_id is not None

    power_state = hass.states.get(power_entity_id)
    assert power_state is not None
    assert power_state.state == "12"
    assert power_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "W"

    energy_state = hass.states.get(energy_entity_id)
    assert energy_state is not None
    assert energy_state.state == "3"
    assert energy_state.attributes[ATTR_UNIT_OF_MEASUREMENT] == "kWh"


async def test_switch_without_metering_does_not_create_power_energy_sensors(
    hass: HomeAssistant,
    vera_component_factory: ComponentFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that non-metered switches do not create power/energy sensors."""
    vera_switch: pv.VeraSwitch = MagicMock(spec=pv.VeraSwitch)
    vera_switch.device_id = 1
    vera_switch.vera_device_id = vera_switch.device_id
    vera_switch.comm_failure = False
    vera_switch.name = "plain_switch"
    vera_switch.category = 0
    vera_switch.power = None
    vera_switch.energy = None

    vera_sensor: pv.VeraSensor = MagicMock(spec=pv.VeraSensor)
    vera_sensor.device_id = 2
    vera_sensor.vera_device_id = vera_sensor.device_id
    vera_sensor.comm_failure = False
    vera_sensor.name = "dummy_sensor"
    vera_sensor.category = pv.CATEGORY_TEMPERATURE_SENSOR
    vera_sensor.temperature = "20"

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            devices=(vera_switch, vera_sensor)
        ),
    )
    await hass.async_block_till_done()

    power_entity_id = entity_registry.async_get_entity_id(
        "sensor", "vera", "vera_1111_1_power"
    )
    energy_entity_id = entity_registry.async_get_entity_id(
        "sensor", "vera", "vera_1111_1_energy"
    )

    assert power_entity_id is None
    assert energy_entity_id is None
