"""Common code for tests."""

from typing import Callable, Dict, List, NamedTuple, Tuple

from mock import MagicMock
import pyvera as pv

from homeassistant.components.vera.const import CONF_BASE_URL, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

SetupCallback = Callable[[pv.VeraController], None]

ControllerData = NamedTuple(
    "ControllerData", (("controller", pv.VeraController), ("update_callback", Callable))
)

ComponentData = NamedTuple(
    "ComponentData", (("controller_datas", Tuple[ControllerData, ...]),)
)

ControllerConfig = NamedTuple(
    "ControllerConfig",
    (
        ("config", Dict),
        ("serial_number", str),
        ("devices", Tuple[pv.VeraDevice, ...]),
        ("scenes", Tuple[pv.VeraScene, ...]),
        ("setup_callback", SetupCallback),
    ),
)


def new_simple_controller_config(
    base_url="http://127.0.0.1:123",
    serial_number="1111",
    devices: Tuple[pv.VeraDevice, ...] = (),
    scenes: Tuple[pv.VeraScene, ...] = (),
    setup_callback: SetupCallback = None,
) -> ControllerConfig:
    """Create simple contorller config."""
    return ControllerConfig(
        config={CONF_BASE_URL: base_url},
        serial_number=serial_number,
        devices=devices,
        scenes=scenes,
        setup_callback=setup_callback,
    )


class ComponentFactory:
    """Factory class."""

    def __init__(self, vera_controller_class_mock):
        """Constructor."""
        self.vera_controller_class_mock = vera_controller_class_mock

    async def configure_component(
        self, hass: HomeAssistant, controller_configs: Tuple[ControllerConfig, ...]
    ) -> ComponentData:
        """Configure the component with specific mock data."""
        hass_config = {
            DOMAIN: [cc.config for cc in controller_configs or []],
        }

        controllers = []
        for controller_config in controller_configs:
            controller = MagicMock(spec=pv.VeraController)  # type: pv.VeraController
            controller.base_url = controller_config.config.get(CONF_BASE_URL)
            controller.register = MagicMock()
            controller.start = MagicMock()
            controller.stop = MagicMock()
            controller.refresh_data = MagicMock()
            controller.temperature_units = "C"
            controller.serial_number = controller_config.serial_number
            controller.get_devices = MagicMock(return_value=controller_config.devices)
            controller.get_scenes = MagicMock(return_value=controller_config.scenes)

            for vera_obj in controller.get_devices() + controller.get_scenes():
                vera_obj.vera_controller = controller

            controller.get_devices.reset_mock()
            controller.get_scenes.reset_mock()

            if controller_config.setup_callback:
                controller_config.setup_callback(controller, hass_config)

            controllers.append(controller)

        self.vera_controller_class_mock.side_effect = controllers

        # Setup home assistant.
        assert await async_setup_component(hass, DOMAIN, hass_config)
        await hass.async_block_till_done()

        controller_datas = []  # type: List[ControllerData]
        for controller in controllers:
            update_callback = (
                controller.register.call_args_list[0][0][1]
                if controller.register.call_args_list
                else None
            )
            controller_datas.append(
                ControllerData(controller=controller, update_callback=update_callback)
            )

        return ComponentData(controller_datas=tuple(controller_datas))
