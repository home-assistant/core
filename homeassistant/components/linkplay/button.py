"""Support for LinkPlay buttons."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from linkplay.bridge import LinkPlayBridge

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LinkPlayConfigEntry
from .entity import LinkPlayBaseEntity, exception_wrap

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class LinkPlayButtonEntityDescription(ButtonEntityDescription):
    """Class describing LinkPlay button entities."""

    remote_function: Callable[[LinkPlayBridge], Coroutine[Any, Any, None]]


BUTTON_TYPES: tuple[LinkPlayButtonEntityDescription, ...] = (
    LinkPlayButtonEntityDescription(
        key="timesync",
        translation_key="timesync",
        remote_function=lambda linkplay_bridge: linkplay_bridge.device.timesync(),
        entity_category=EntityCategory.CONFIG,
    ),
    LinkPlayButtonEntityDescription(
        key="restart",
        device_class=ButtonDeviceClass.RESTART,
        remote_function=lambda linkplay_bridge: linkplay_bridge.device.reboot(),
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinkPlayConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the LinkPlay buttons from config entry."""

    # add entities
    async_add_entities(
        LinkPlayButton(config_entry.runtime_data.bridge, description)
        for description in BUTTON_TYPES
    )


class LinkPlayButton(LinkPlayBaseEntity, ButtonEntity):
    """Representation of LinkPlay button."""

    entity_description: LinkPlayButtonEntityDescription

    def __init__(
        self,
        bridge: LinkPlayBridge,
        description: LinkPlayButtonEntityDescription,
    ) -> None:
        """Initialize LinkPlay button."""
        super().__init__(bridge)
        self.entity_description = description
        self._attr_unique_id = f"{bridge.device.uuid}-{description.key}"

    @exception_wrap
    async def async_press(self) -> None:
        """Press the button."""
        await self.entity_description.remote_function(self._bridge)
