"""Vera tests."""
from typing import Any, Callable, Tuple

import pyvera as pv

from homeassistant.const import UNIT_PERCENTAGE
from homeassistant.core import HomeAssistant

from .common import ComponentFactory, new_simple_controller_config

from tests.async_mock import MagicMock


async def run_sensor_test(
    hass: HomeAssistant,
    vera_component_factory: ComponentFactory,
    category: int,
    class_property: str,
    assert_states: Tuple[Tuple[Any, Any]],
    assert_unit_of_measurement: str = None,
    setup_callback: Callable[[pv.VeraController], None] = None,
) -> None:
    """Test generic sensor."""
    vera_device = MagicMock(spec=pv.VeraSensor)  # type: pv.VeraSensor
    vera_device.device_id = 1
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
    update_callback = component_data.controller_data.update_callback

    for (initial_value, state_value) in assert_states:
        setattr(vera_device, class_property, initial_value)
        update_callback(vera_device)
        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state.state == state_value
        if assert_unit_of_measurement:
            assert state.attributes["unit_of_measurement"] == assert_unit_of_measurement


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
        assert_states=(("33", "1"), ("44", "7")),
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
        assert_states=(("33", "33"), ("44", "44")),
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
        assert_unit_of_measurement="lx",
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
        assert_unit_of_measurement=UNIT_PERCENTAGE,
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
        assert_unit_of_measurement="watts",
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
    vera_device = MagicMock(spec=pv.VeraSensor)  # type: pv.VeraSensor
    vera_device.device_id = 1
    vera_device.name = "dev1"
    vera_device.category = pv.CATEGORY_SCENE_CONTROLLER
    vera_device.get_last_scene_id = MagicMock(return_value="id0")
    vera_device.get_last_scene_time = MagicMock(return_value="0000")
    entity_id = "sensor.dev1_1"

    component_data = await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(devices=(vera_device,)),
    )
    update_callback = component_data.controller_data.update_callback

    vera_device.get_last_scene_time.return_value = "1111"
    update_callback(vera_device)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "id0"
