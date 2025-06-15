"""Support for LinkPlay select."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from linkplay.bridge import LinkPlayPlayer
from linkplay.consts import AudioOutputHwMode
from linkplay.manufacturers import MANUFACTURER_WIIM

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LinkPlayConfigEntry
from .entity import LinkPlayBaseEntity, exception_wrap

_LOGGER = logging.getLogger(__name__)

AUDIO_OUTPUT_HW_MODE_MAP: dict[AudioOutputHwMode, str] = {
    AudioOutputHwMode.OPTICAL: "Optical",
    AudioOutputHwMode.LINE_OUT: "Line Out",
    AudioOutputHwMode.COAXIAL: "Coaxial",
    AudioOutputHwMode.HEADPHONES: "Headphones",
}

AUDIO_OUTPUT_HW_MODE_MAP_INV: dict[str, AudioOutputHwMode] = {
    v: k for k, v in AUDIO_OUTPUT_HW_MODE_MAP.items()
}


@dataclass(frozen=True, kw_only=True)
class LinkPlaySelectEntityDescription(SelectEntityDescription):
    """Class describing LinkPlay select entities."""

    remote_fn: Callable[[LinkPlayPlayer, Any], Coroutine[Any, Any, None]]
    current_option_fn: Callable[[LinkPlayPlayer], Awaitable[Any]]


SELECT_TYPES_WIIM: tuple[LinkPlaySelectEntityDescription, ...] = (
    LinkPlaySelectEntityDescription(
        key="audio_output_hardware_mode",
        translation_key="audio_output_hardware_mode",
        current_option_fn=lambda linkplay_bridge: linkplay_bridge.player.get_audio_output_hw_mode(),
        remote_fn=lambda linkplay_bridge,
        option: linkplay_bridge.player.set_audio_output_hw_mode(
            AUDIO_OUTPUT_HW_MODE_MAP_INV[option]
        ),
        options=list(AUDIO_OUTPUT_HW_MODE_MAP_INV),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LinkPlayConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the LinkPlay select from config entry."""

    # add entities
    if config_entry.runtime_data.bridge.device.manufacturer == MANUFACTURER_WIIM:
        async_add_entities(
            LinkPlaySelect(config_entry.runtime_data.bridge, description)
            for description in SELECT_TYPES_WIIM
        )


class LinkPlaySelect(LinkPlayBaseEntity, SelectEntity):
    """Representation of LinkPlay select."""

    entity_description: LinkPlaySelectEntityDescription

    def __init__(
        self,
        bridge: LinkPlayPlayer,
        description: LinkPlaySelectEntityDescription,
    ) -> None:
        """Initialize LinkPlay select."""
        super().__init__(bridge)
        self.entity_description = description
        self._attr_unique_id = f"{bridge.device.uuid}-{description.key}"

    async def async_update(self) -> None:
        """Get the current value from the device."""
        try:
            response = await self.entity_description.current_option_fn(self._bridge)
            self._attr_current_option = AUDIO_OUTPUT_HW_MODE_MAP[response.hardware]
        except ValueError as ex:
            _LOGGER.debug(
                "Cannot retrieve hardware mode value from device with error:, %s", ex
            )
            self._attr_current_option = None

    @exception_wrap
    async def async_select_option(self, option: str) -> None:
        """Set the option."""
        await self.entity_description.remote_fn(self._bridge, option)
        self._attr_current_option = option
