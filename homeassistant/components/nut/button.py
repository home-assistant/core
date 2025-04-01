"""Provides a switch for switchable NUT outlets."""

from __future__ import annotations

import logging

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NutConfigEntry
from .entity import NUTBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


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
        outlet_name: str = status.get(f"outlet.{outlet_num_str}.name") or outlet_num_str
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
        NUTButton(coordinator, description, data, unique_id)
        for button_id, description in valid_button_types.items()
        if button_id in pynut_data.user_available_commands
    )


class NUTButton(NUTBaseEntity, ButtonEntity):
    """Representation of a button entity for NUT."""

    async def async_press(self) -> None:
        """Press the button."""
        name_list = self.entity_description.key.split(".")
        command_name = f"{name_list[0]}.{name_list[1]}.load.cycle"
        await self.pynut_data.async_run_command(command_name)
