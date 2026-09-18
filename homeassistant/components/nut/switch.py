"""Provides a switch for switchable NUT outlets."""

import logging
from typing import Any, override

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import outlet_numbers_from_status
from .coordinator import NutConfigEntry
from .entity import NUTBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NutConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the NUT switches."""
    pynut_data = config_entry.runtime_data
    coordinator = pynut_data.coordinator
    status = coordinator.data
    data = pynut_data.data
    unique_id = pynut_data.unique_id
    user_available_commands = pynut_data.user_available_commands

    switch_descriptions = [
        SwitchEntityDescription(
            key=f"outlet.{outlet_num}.load.poweronoff",
            translation_key="outlet_number_load_poweronoff",
            translation_placeholders={
                "outlet_name": (
                    status.get(f"outlet.{outlet_num}.name")
                    or status.get(f"outlet.{outlet_num}.desc")
                    or str(outlet_num)
                )
            },
            device_class=SwitchDeviceClass.OUTLET,
        )
        for outlet_num in sorted(outlet_numbers_from_status(status))
        if (
            status.get(f"outlet.{outlet_num}.switchable") == "yes"
            and f"outlet.{outlet_num}.load.on" in user_available_commands
            and f"outlet.{outlet_num}.load.off" in user_available_commands
        )
    ]

    async_add_entities(
        NUTSwitch(coordinator, description, data, unique_id)
        for description in switch_descriptions
    )


class NUTSwitch(NUTBaseEntity, SwitchEntity):
    """Representation of a switch entity for NUT status values."""

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        status = self.coordinator.data
        outlet, outlet_num_str = self.entity_description.key.split(".", 2)[:2]
        if (state := status.get(f"{outlet}.{outlet_num_str}.status")) is None:
            return None
        return bool(state == "on")

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        outlet, outlet_num_str = self.entity_description.key.split(".", 2)[:2]
        command_name = f"{outlet}.{outlet_num_str}.load.on"
        await self.pynut_data.async_run_command(command_name)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        outlet, outlet_num_str = self.entity_description.key.split(".", 2)[:2]
        command_name = f"{outlet}.{outlet_num_str}.load.off"
        await self.pynut_data.async_run_command(command_name)
