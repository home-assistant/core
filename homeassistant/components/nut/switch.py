"""Provides a switch for switchable NUT outlets."""

from __future__ import annotations

from contextlib import suppress
import logging
import re
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

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: NutConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    
    _LOGGER.warning("NUT switch platform loaded")
    
    """Set up the NUT switches."""
    pynut_data = config_entry.runtime_data
    coordinator = pynut_data.coordinator
    status = coordinator.data

    data = pynut_data.data
    unique_id = pynut_data.unique_id
    user_available_commands = pynut_data.user_available_commands

    outlet_numbers: set[int] = set()

    # Prefer outlet.count
    if (num_outlets := status.get("outlet.count")) is not None:
        with suppress(ValueError):
            outlet_numbers.update(range(1, int(num_outlets) + 1))

# Detect outlets from status
    for key in status:
        match = re.match(r"outlet\.(\d+)\.status", key)
        if match:
            outlet_numbers.add(int(match.group(1)))

# Detect outlets from commands
    for cmd in map(str, user_available_commands):
        match = re.match(r"outlet\.(\d+)\.load\.(on|off)", cmd)
        if match:
            outlet_numbers.add(int(match.group(1)))

    cmds = set(map(str, user_available_commands))

    switch_descriptions: list[SwitchEntityDescription] = []

    for outlet_num in sorted(outlet_numbers):
        if (
            f"outlet.{outlet_num}.load.on" in cmds
            or "load.on" in cmds
        ):
            switch_descriptions.append(
                SwitchEntityDescription(
                    key=f"outlet.{outlet_num}.load.poweronoff",
                    translation_key="outlet_number_load_poweronoff",
                    translation_placeholders={
                        "outlet_name": status.get(f"outlet.{outlet_num}.name")
                        or status.get(f"outlet.{outlet_num}.desc")
                        or str(outlet_num)
                    },
                    device_class=SwitchDeviceClass.OUTLET,
                )
            )

    async_add_entities(
        NUTSwitch(coordinator, description, data, unique_id)
        for description in switch_descriptions
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
        return bool(state == "on")

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
