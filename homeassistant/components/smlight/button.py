"""Support for SLZB-06 buttons."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from typing import Final

from pysmlight.web import CmdWrapper

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SmDataUpdateCoordinator
from .entity import SmEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class SmButtonDescription(ButtonEntityDescription):
    """Class to describe a Button entity."""

    press_fn: Callable[[CmdWrapper], Awaitable[None]]


BUTTONS: Final = [
    SmButtonDescription(
        key="core_restart",
        translation_key="core_restart",
        device_class=ButtonDeviceClass.RESTART,
        press_fn=lambda cmd: cmd.reboot(),
    ),
    SmButtonDescription(
        key="zigbee_restart",
        translation_key="zigbee_restart",
        device_class=ButtonDeviceClass.RESTART,
        press_fn=lambda cmd: cmd.zb_restart(),
    ),
    SmButtonDescription(
        key="zigbee_flash_mode",
        translation_key="zigbee_flash_mode",
        entity_registry_enabled_default=False,
        press_fn=lambda cmd: cmd.zb_bootloader(),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SMLIGHT buttons based on a config entry."""
    coordinator = entry.runtime_data

    async_add_entities(SmButton(coordinator, button) for button in BUTTONS)


class SmButton(SmEntity, ButtonEntity):
    """Defines a SLZB-06 button."""

    entity_description: SmButtonDescription
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: SmDataUpdateCoordinator,
        description: SmButtonDescription,
    ) -> None:
        """Initialize SLZB-06 button entity."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.unique_id}-{description.key}"

    async def async_press(self) -> None:
        """Trigger button press."""
        await self.entity_description.press_fn(self.coordinator.client.cmds)
