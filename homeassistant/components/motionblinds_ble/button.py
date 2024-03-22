"""Button entities for the Motionblinds BLE integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from motionblindsble.device import MotionDevice

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_CONNECT,
    ATTR_DISCONNECT,
    ATTR_FAVORITE,
    CONF_MAC_CODE,
    DOMAIN,
    ICON_CONNECT,
    ICON_DISCONNECT,
    ICON_FAVORITE,
)
from .entity import MotionblindsBLEEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class MotionblindsBLEButtonEntityDescription(ButtonEntityDescription):
    """Entity description of a button entity with command attribute."""

    command: Callable[[MotionDevice], Coroutine[Any, Any, None]] | None = None


BUTTON_TYPES: dict[str, MotionblindsBLEButtonEntityDescription] = {
    ATTR_CONNECT: MotionblindsBLEButtonEntityDescription(
        key=ATTR_CONNECT,
        translation_key=ATTR_CONNECT,
        icon=ICON_CONNECT,
        entity_category=EntityCategory.CONFIG,
        command=lambda device: device.connect(),
    ),
    ATTR_DISCONNECT: MotionblindsBLEButtonEntityDescription(
        key=ATTR_DISCONNECT,
        translation_key=ATTR_DISCONNECT,
        icon=ICON_DISCONNECT,
        entity_category=EntityCategory.CONFIG,
        command=lambda device: device.disconnect(),
    ),
    ATTR_FAVORITE: MotionblindsBLEButtonEntityDescription(
        key=ATTR_FAVORITE,
        translation_key=ATTR_FAVORITE,
        icon=ICON_FAVORITE,
        entity_category=EntityCategory.CONFIG,
        command=lambda device: device.favorite(),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up button entities based on a config entry."""

    device: MotionDevice = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            MotionblindsBLEButtonEntity(
                device,
                entry,
                entity_description,
                unique_id_suffix=entity_description.key,
            )
            for entity_description in BUTTON_TYPES.values()
        ]
    )


class MotionblindsBLEButtonEntity(MotionblindsBLEEntity, ButtonEntity):
    """Representation of a command button entity."""

    entity_description: MotionblindsBLEButtonEntityDescription

    async def async_added_to_hass(self) -> None:
        """Log button entity information."""
        _LOGGER.info(
            "(%s) Setting up %s button entity",
            self.entry.data[CONF_MAC_CODE],
            self.entity_description.key,
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        if callable(self.entity_description.command):
            await self.entity_description.command(self.device)
