"""Common code for tests."""

from typing import Callable, NamedTuple, Tuple

from mock import MagicMock, patch
from pyvera import VeraController, VeraDevice, VeraScene

from homeassistant.components.vera import CONF_CONTROLLER, DOMAIN
from homeassistant.const import CONF_UNIT_SYSTEM, CONF_UNIT_SYSTEM_METRIC
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

ComponentData = NamedTuple("ComponentData", (("controller", VeraController),))


async def async_configure_component(
    hass: HomeAssistant,
    devices: Tuple[VeraDevice] = (),
    scenes: Tuple[VeraScene] = (),
    setup_callback: Callable[[VeraController], None] = None,
) -> ComponentData:
    """Configure the component with specific mock data."""
    controller_url = "http://127.0.0.1:123"

    hass_config = {
        "homeassistant": {CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC},
        DOMAIN: {CONF_CONTROLLER: controller_url},
    }

    controller = MagicMock(spec=VeraController)  # type: VeraController
    controller.base_url = controller_url
    controller.register = MagicMock()
    controller.get_devices = MagicMock(return_value=devices or ())
    controller.get_scenes = MagicMock(return_value=scenes or ())

    for vera_obj in controller.get_devices() + controller.get_scenes():
        vera_obj.vera_controller = controller

    controller.get_devices.reset_mock()
    controller.get_scenes.reset_mock()

    if setup_callback:
        setup_callback(controller, hass_config)

    def init_controller(base_url: str) -> list:
        nonlocal controller
        return [controller, True]

    patch("pyvera.init_controller", side_effect=init_controller).start()

    # Setup home assistant.
    assert await async_setup_component(hass, DOMAIN, hass_config)
    await hass.async_block_till_done()

    return ComponentData(controller=controller)
