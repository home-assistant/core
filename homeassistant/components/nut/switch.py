"""Provides a switch for switchable NUT outlets."""

from contextlib import suppress
import logging
from typing import Any

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

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

    outlet_numbers: set[int] = set()

    # Prefer outlet.count when available
    if (num_outlets := status.get("outlet.count")) is not None:
        with suppress(ValueError):
            outlet_numbers.update(range(1, int(num_outlets) + 1))

    # Detect outlets from status keys (outlet.<n>.status)
    prefix = "outlet."
    for key in status:
        rest = key.removeprefix(prefix)
        if rest != key and rest.endswith(".status"):
            num = rest[: -len(".status")]
            if num.isdigit():
                outlet_numbers.add(int(num))

    # Detect outlets from available commands (outlet.<n>.load.on/off)
    cmds = set(user_available_commands)
    for cmd in cmds:
        rest = cmd.removeprefix(prefix)
        if rest != cmd and rest.endswith((".load.on", ".load.off")):
            num = rest.split(".", 1)[0]
            if num.isdigit():
                outlet_numbers.add(int(num))

    switch_descriptions = [
        SwitchEntityDescription(
            key=f"outlet.{outlet_num}.load.poweronoff",
            translation_key="outlet_number_load_poweronoff",
            translation_placeholders={
                "outlet_name": status.get(f"outlet.{outlet_num}.name")
                or str(outlet_num)
            },
            device_class=SwitchDeviceClass.OUTLET,
        )
        for outlet_num in sorted(outlet_numbers)
        if (
            f"outlet.{outlet_num}.load.on" in cmds
            and f"outlet.{outlet_num}.load.off" in cmds
        )
    ]

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
