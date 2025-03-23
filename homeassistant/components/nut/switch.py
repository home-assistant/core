"""Provides a switch for switchable NUT outlets."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NutConfigEntry
from .entity import NUTBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NutConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the NUT switches."""
    available_switch_types: dict[str, SwitchEntityDescription] = {}

    pynut_data = config_entry.runtime_data
    coordinator = pynut_data.coordinator
    status = coordinator.data

    # Dynamically add outlet switch types
    if (num_outlets := status.get("outlet.count")) is None:
        return

    data = pynut_data.data
    unique_id = pynut_data.unique_id
    for outlet_num in range(1, int(num_outlets) + 1):
        outlet_num_str = str(outlet_num)
        outlet_name: str = status.get(f"outlet.{outlet_num_str}.name") or outlet_num_str

        # Add when outlet is switchable and both on and off are available
        if (
            (status.get(f"outlet.{outlet_num_str}.switchable") == "yes")
            and (
                f"outlet.{outlet_num_str}.load.on" in pynut_data.user_available_commands
            )
            and (
                f"outlet.{outlet_num_str}.load.off"
                in pynut_data.user_available_commands
            )
        ):
            available_switch_types |= {
                f"outlet.{outlet_num_str}.load.poweronoff": SwitchEntityDescription(
                    key=f"outlet.{outlet_num_str}.load.poweronoff",
                    translation_key="outlet_number_load_poweronoff",
                    translation_placeholders={"outlet_name": outlet_name},
                    device_class=SwitchDeviceClass.OUTLET,
                    entity_registry_enabled_default=True,
                ),
            }

    async_add_entities(
        NUTSwitch(
            coordinator,
            available_switch_types[switch_type],
            data,
            unique_id,
        )
        for switch_type in available_switch_types
    )


class NUTSwitch(NUTBaseEntity, SwitchEntity):
    """Representation of a switch entity for NUT status values."""

    @property
    def is_on(self) -> bool | None:
        """Return the state of the switch."""
        status = self.coordinator.data
        outlet, outlet_num_str = self.entity_description.key.split(".", 2)[:2]
        if (state := status.get(f"{outlet}.{outlet_num_str}.status")) is None:
            return None
        return state == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""

        outlet, outlet_num_str = self.entity_description.key.split(".", 2)[:2]
        command_name = f"{outlet}.{outlet_num_str}.load.on"
        await self.pynut_data.async_run_command(command_name)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""

        outlet, outlet_num_str = self.entity_description.key.split(".", 2)[:2]
        command_name = f"{outlet}.{outlet_num_str}.load.off"
        await self.pynut_data.async_run_command(command_name)
