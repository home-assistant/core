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
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RainMachineEntity
from .const import DATA_CONTROLLER, DATA_COORDINATOR, DATA_PROVISION_SETTINGS, DOMAIN


@dataclass
class RainMachineButtonDescriptionMixin:
    """Define an entity description mixin for RainMachine buttons."""

    push_action: Callable[[Controller], Awaitable]


@dataclass
class RainMachineButtonDescription(
    ButtonEntityDescription, RainMachineButtonDescriptionMixin
):
    """Describe a RainMachine button description."""


BUTTON_KIND_REBOOT = "reboot"


async def _async_reboot(controller: Controller) -> None:
    """Reboot the RainMachine."""
    await controller.machine.reboot()


BUTTON_DESCRIPTIONS = (
    RainMachineButtonDescription(
        key=BUTTON_KIND_REBOOT,
        name="Reboot",
        push_action=_async_reboot,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up RainMachine buttons based on a config entry."""
    async_add_entities(
        [
            RainMachineButton(
                entry,
                # We don't actually need this coordinator; we pass it because the
                # RainMachineEntity class requires one.
                hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR][
                    DATA_PROVISION_SETTINGS
                ],
                hass.data[DOMAIN][entry.entry_id][DATA_CONTROLLER],
                description,
            )
            for description in BUTTON_DESCRIPTIONS
        ]
    )


class RainMachineButton(RainMachineEntity, ButtonEntity):
    """Define a RainMachine button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    entity_description: RainMachineButtonDescription

    async def async_press(self) -> None:
        """Send out a restart command."""
        try:
            await self.entity_description.push_action(self._controller)
        except RainMachineError as err:
            raise HomeAssistantError(
                f'Error while pressing button "{self.entity_id}": {err}'
            ) from err

        async_dispatcher_send(self.hass, self._signal_reboot_requested)
