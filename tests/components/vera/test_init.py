"""Vera tests."""
from unittest.mock import MagicMock

from pyvera import VeraBinarySensor

from homeassistant.components.vera import DOMAIN, async_unload_entry
from homeassistant.core import HomeAssistant

from .common import ComponentFactory, new_simple_controller_config


async def test_init(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device1 = MagicMock(spec=VeraBinarySensor)  # type: VeraBinarySensor
    vera_device1.device_id = 1
    vera_device1.vera_device_id = 1
    vera_device1.name = "first_dev"
    vera_device1.is_tripped = False
    entity1_id = "binary_sensor.first_dev_1"

    vera_device2 = MagicMock(spec=VeraBinarySensor)  # type: VeraBinarySensor
    vera_device2.device_id = 2
    vera_device2.vera_device_id = 2
    vera_device2.name = "second_dev"
    vera_device2.is_tripped = False
    entity2_id = "binary_sensor.second_dev_2"

    await vera_component_factory.configure_component(
        hass=hass,
        controller_configs=(
            new_simple_controller_config(
                base_url="http://127.0.0.1:111",
                serial_number="first_serial",
                devices=(vera_device1,),
            ),
            new_simple_controller_config(
                base_url="http://127.0.0.1:222",
                serial_number="second_serial",
                devices=(vera_device2,),
            ),
        ),
    )

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    entry1 = entity_registry.async_get(entity1_id)
    entry2 = entity_registry.async_get(entity2_id)

    assert entry1
    assert entry1.unique_id == "first_serial_1"

    assert entry2
    assert entry2.unique_id == "second_serial_2"


async def test_unload(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device1 = MagicMock(spec=VeraBinarySensor)  # type: VeraBinarySensor
    vera_device1.device_id = 1
    vera_device1.vera_device_id = 1
    vera_device1.name = "first_dev"
    vera_device1.is_tripped = False

    component_data = await vera_component_factory.configure_component(
        hass=hass, controller_configs=(new_simple_controller_config(),)
    )
    component_data.controller_datas[0].controller.stop()

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert config_entries

    for config_entry in config_entries:
        await async_unload_entry(hass, config_entry)
