"""Provides a switch for switchable NUT outlets."""

from __future__ import annotations

import logging

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NutConfigEntry, PyNUTData
from .const import DOMAIN
from .sensor import _get_nut_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NutConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the NUT buttons."""
    pynut_data = config_entry.runtime_data
    coordinator = pynut_data.coordinator
    status = coordinator.data

    # Dynamically add outlet button types
    if (num_outlets := status.get("outlet.count")) is None:
        return

    data = pynut_data.data
    unique_id = pynut_data.unique_id
    valid_button_types: dict[str, ButtonEntityDescription] = {}
    for outlet_num in range(1, int(num_outlets) + 1):
        outlet_num_str = str(outlet_num)
        outlet_name: str = (
            status.get(f"outlet.{outlet_num_str}.name") or outlet_num_str
        )
        valid_button_types |= {
            f"outlet.{outlet_num_str}.load.cycle": ButtonEntityDescription(
                key=f"outlet.{outlet_num_str}.load.cycle",
                translation_key="outlet_number_load_cycle",
                translation_placeholders={"outlet_name": outlet_name},
                device_class=ButtonDeviceClass.RESTART,
                entity_registry_enabled_default=True,
            ),
        }

    async_add_entities(
        NUTButton(description,data,unique_id)
        for button_id, description in valid_button_types.items()
        if button_id in pynut_data.user_available_commands
    )


class NUTButton(ButtonEntity):
    """Representation of a button entity for NUT."""

    _attr_has_entity_name = True

    def __init__(
        self,
        button_description: ButtonEntityDescription,
        data: PyNUTData,
        unique_id: str,
    ) -> None:
        """Initialize the button."""
        self.pynut_data = data
        self.entity_description = button_description

        device_name = data.name.title()
        self._attr_unique_id = f"{unique_id}_{button_description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=device_name,
        )
        self._attr_device_info.update(_get_nut_device_info(data))

    async def async_press(self) -> None:
        """Press the button."""
        name_list = self.entity_description.key.split(".")
        command_name = f"{name_list[0]}.{name_list[1]}.load.cycle"
        await self.pynut_data.async_run_command(command_name)
