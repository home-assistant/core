"""Vera tests."""
from unittest.mock import MagicMock

from pyvera import VeraBinarySensor, VeraController
from requests.exceptions import RequestException

from homeassistant.components.vera import (
    CONF_CONTROLLER,
    DOMAIN,
    ControllerData,
    async_setup_entry,
    async_unload_entry,
)
from homeassistant.config_entries import ConfigEntry
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

    await vera_component_factory.configure_component(
        hass=hass,
        controller_config=new_simple_controller_config(
            base_url="http://127.0.0.1:111",
            serial_number="first_serial",
            devices=(vera_device1,),
        ),
    )

    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    entry1 = entity_registry.async_get(entity1_id)

    assert entry1


async def test_unload(
    hass: HomeAssistant, vera_component_factory: ComponentFactory
) -> None:
    """Test function."""
    vera_device1 = MagicMock(spec=VeraBinarySensor)  # type: VeraBinarySensor
    vera_device1.device_id = 1
    vera_device1.vera_device_id = 1
    vera_device1.name = "first_dev"
    vera_device1.is_tripped = False

    await vera_component_factory.configure_component(
        hass=hass, controller_config=new_simple_controller_config()
    )

    config_entries = hass.config_entries.async_entries(DOMAIN)
    assert config_entries

    for config_entry in config_entries:
        await async_unload_entry(hass, config_entry)


async def test_async_setup_entry_error(hass: HomeAssistant) -> None:
    """Test function."""
    controller = MagicMock(spec=VeraController)  # type: VeraController
    controller.get_devices.side_effect = RequestException()
    controller.get_scenes.side_effect = RequestException()

    hass.data[DOMAIN] = ControllerData(controller=controller, devices={}, scenes=())

    entry = MagicMock(spec=ConfigEntry)  # type: ConfigEntry
    entry.data = {CONF_CONTROLLER: "http://127.0.0.1"}

    assert not await async_setup_entry(hass, entry)
