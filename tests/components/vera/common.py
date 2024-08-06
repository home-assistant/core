"""Common code for tests."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import NamedTuple
from unittest.mock import MagicMock

import pyvera as pv

from homeassistant import config_entries
from homeassistant.components.vera.const import (
    CONF_CONTROLLER,
    CONF_LEGACY_UNIQUE_ID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

type SetupCallback = Callable[[pv.VeraController, dict], None]


class ControllerData(NamedTuple):
    """Test data about a specific vera controller."""

    controller: pv.VeraController
    update_callback: Callable


class ComponentData(NamedTuple):
    """Test data about the vera component."""

    controller_data: tuple[ControllerData]


class ConfigSource(Enum):
    """Source of configuration."""

    FILE = "file"
    CONFIG_FLOW = "config_flow"
    CONFIG_ENTRY = "config_entry"


class ControllerConfig(NamedTuple):
    """Test config for mocking a vera controller."""

    config: dict
    options: dict
    config_source: ConfigSource
    serial_number: str
    devices: tuple[pv.VeraDevice, ...]
    scenes: tuple[pv.VeraScene, ...]
    setup_callback: SetupCallback
    legacy_entity_unique_id: bool


def new_simple_controller_config(
    config: dict | None = None,
    options: dict | None = None,
    config_source=ConfigSource.CONFIG_FLOW,
    serial_number="1111",
    devices: tuple[pv.VeraDevice, ...] = (),
    scenes: tuple[pv.VeraScene, ...] = (),
    setup_callback: SetupCallback = None,
    legacy_entity_unique_id=False,
) -> ControllerConfig:
    """Create simple controller config."""
    return ControllerConfig(
        config=config or {CONF_CONTROLLER: "http://127.0.0.1:123"},
        options=options,
        config_source=config_source,
        serial_number=serial_number,
        devices=devices,
        scenes=scenes,
        setup_callback=setup_callback,
        legacy_entity_unique_id=legacy_entity_unique_id,
    )


class ComponentFactory:
    """Factory class."""

    def __init__(self, vera_controller_class_mock):
        """Initialize the factory."""
        self.vera_controller_class_mock = vera_controller_class_mock

    async def configure_component(
        self,
        hass: HomeAssistant,
        controller_config: ControllerConfig = None,
        controller_configs: tuple[ControllerConfig] = (),
    ) -> ComponentData:
        """Configure the component with multiple specific mock data."""
        configs = list(controller_configs)

        if controller_config:
            configs.append(controller_config)

        return ComponentData(
            controller_data=tuple(
                [
                    await self._configure_component(hass, controller_config)
                    for controller_config in configs
                ]
            )
        )

    async def _configure_component(
        self, hass: HomeAssistant, controller_config: ControllerConfig
    ) -> ControllerData:
        """Configure the component with specific mock data."""
        component_config = {
            **(controller_config.config or {}),
            **(controller_config.options or {}),
        }

        if controller_config.legacy_entity_unique_id:
            component_config[CONF_LEGACY_UNIQUE_ID] = True

        controller: pv.VeraController = MagicMock()
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
        if controller_config.config_source == ConfigSource.FILE:
            hass_config[DOMAIN] = component_config

        # Setup Home Assistant.
        assert await async_setup_component(hass, DOMAIN, hass_config)
        await hass.async_block_till_done()

        # Setup component through config flow.
        if controller_config.config_source == ConfigSource.CONFIG_FLOW:
            await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
                data=component_config,
            )
            await hass.async_block_till_done()

        # Setup component directly from config entry.
        if controller_config.config_source == ConfigSource.CONFIG_ENTRY:
            entry = MockConfigEntry(
                domain=DOMAIN,
                data=controller_config.config,
                options=controller_config.options,
                unique_id="12345",
            )
            entry.add_to_hass(hass)

            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        update_callback = (
            controller.register.call_args_list[0][0][1]
            if controller.register.call_args_list
            else None
        )

        return ControllerData(controller=controller, update_callback=update_callback)
