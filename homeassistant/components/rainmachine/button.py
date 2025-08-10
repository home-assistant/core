"""Buttons for the RainMachine integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from regenmaschine.controller import Controller
from regenmaschine.errors import RainMachineError

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import RainMachineConfigEntry
from .const import DATA_PROVISION_SETTINGS
from .entity import RainMachineEntity, RainMachineEntityDescription


@dataclass(frozen=True, kw_only=True)
class RainMachineButtonDescription(
    ButtonEntityDescription, RainMachineEntityDescription
):
    """Describe a RainMachine button description."""

    push_action: Callable[[Controller], Awaitable]


BUTTON_KIND_REBOOT = "reboot"


async def _async_reboot(controller: Controller) -> None:
    """Reboot the RainMachine."""
    await controller.machine.reboot()


BUTTON_DESCRIPTIONS = (
    RainMachineButtonDescription(
        key=BUTTON_KIND_REBOOT,
        api_category=DATA_PROVISION_SETTINGS,
        push_action=_async_reboot,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RainMachineConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up RainMachine buttons based on a config entry."""
    data = entry.runtime_data
    async_add_entities(
        RainMachineButton(entry, data, description)
        for description in BUTTON_DESCRIPTIONS
    )


class RainMachineButton(RainMachineEntity, ButtonEntity):
    """Define a RainMachine button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    entity_description: RainMachineButtonDescription

    async def async_press(self) -> None:
        """Send out a restart command."""
        try:
            await self.entity_description.push_action(self._data.controller)
        except RainMachineError as err:
            raise HomeAssistantError(
                f'Error while pressing button "{self.entity_id}": {err}'
            ) from err

        async_dispatcher_send(self.hass, self.coordinator.signal_reboot_requested)
