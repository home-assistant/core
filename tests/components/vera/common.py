"""Common code for tests."""

from typing import Callable, Dict, NamedTuple, Tuple

import pyvera as pv

from homeassistant.components.vera.const import CONF_CONTROLLER, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.async_mock import MagicMock
from tests.common import MockConfigEntry

SetupCallback = Callable[[pv.VeraController, dict], None]


class ControllerData(NamedTuple):
    """Test data about a specific vera controller."""

    controller: pv.VeraController
    update_callback: Callable


class ComponentData(NamedTuple):
    """Test data about the vera component."""

    controller_data: ControllerData


class ControllerConfig(NamedTuple):
    """Test config for mocking a vera controller."""

    config: Dict
    options: Dict
    config_from_file: bool
    serial_number: str
    devices: Tuple[pv.VeraDevice, ...]
    scenes: Tuple[pv.VeraScene, ...]
    setup_callback: SetupCallback


def new_simple_controller_config(
    config: dict = None,
    options: dict = None,
    config_from_file=False,
    serial_number="1111",
    devices: Tuple[pv.VeraDevice, ...] = (),
    scenes: Tuple[pv.VeraScene, ...] = (),
    setup_callback: SetupCallback = None,
) -> ControllerConfig:
    """Create simple contorller config."""
    return ControllerConfig(
        config=config or {CONF_CONTROLLER: "http://127.0.0.1:123"},
        options=options,
        config_from_file=config_from_file,
        serial_number=serial_number,
        devices=devices,
        scenes=scenes,
        setup_callback=setup_callback,
    )


class ComponentFactory:
    """Factory class."""

    def __init__(self, vera_controller_class_mock):
        """Initialize the factory."""
        self.vera_controller_class_mock = vera_controller_class_mock

    async def configure_component(
        self, hass: HomeAssistant, controller_config: ControllerConfig
    ) -> ComponentData:
        """Configure the component with specific mock data."""
        component_config = {
            **(controller_config.config or {}),
            **(controller_config.options or {}),
        }

        controller = MagicMock(spec=pv.VeraController)  # type: pv.VeraController
        controller.base_url = component_config.get(CONF_CONTROLLER)
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
            controller_config.setup_callback(controller)

        self.vera_controller_class_mock.return_value = controller

        hass_config = {}

        # Setup component through config file import.
        if controller_config.config_from_file:
            hass_config[DOMAIN] = component_config

        # Setup Home Assistant.
        assert await async_setup_component(hass, DOMAIN, hass_config)
        await hass.async_block_till_done()

        # Setup component through config flow.
        if not controller_config.config_from_file:
            entry = MockConfigEntry(
                domain=DOMAIN, data=component_config, options={}, unique_id="12345"
            )
            entry.add_to_hass(hass)

            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        update_callback = (
            controller.register.call_args_list[0][0][1]
            if controller.register.call_args_list
            else None
        )

        return ComponentData(
            controller_data=ControllerData(
                controller=controller, update_callback=update_callback
            )
        )
