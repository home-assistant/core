"""Support for ZHA button."""
from __future__ import annotations

import abc
import functools
import logging
from typing import Any

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import discovery
from .core.const import CHANNEL_IDENTIFY, DATA_ZHA, SIGNAL_ADD_ENTITIES
from .core.registries import ZHA_ENTITIES
from .core.typing import ChannelType, ZhaDeviceType
from .entity import ZhaEntity

MULTI_MATCH = functools.partial(ZHA_ENTITIES.multipass_match, Platform.BUTTON)
DEFAULT_DURATION = 5  # seconds

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation button from config entry."""
    entities_to_create = hass.data[DATA_ZHA][Platform.BUTTON]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            discovery.async_add_entities,
            async_add_entities,
            entities_to_create,
            update_before_add=False,
        ),
    )
    config_entry.async_on_unload(unsub)


class ZHAButton(ZhaEntity, ButtonEntity):
    """Defines a ZHA button."""

    _command_name: str = None

    def __init__(
        self,
        unique_id: str,
        zha_device: ZhaDeviceType,
        channels: list[ChannelType],
        **kwargs,
    ) -> None:
        """Init this button."""
        super().__init__(unique_id, zha_device, channels, **kwargs)
        self._channel: ChannelType = channels[0]

    @abc.abstractmethod
    def get_args(self) -> list[Any]:
        """Return the arguments to use in the command."""

    async def async_press(self) -> None:
        """Send out a update command."""
        command = getattr(self._channel, self._command_name)
        arguments = self.get_args()
        await command(*arguments)


@MULTI_MATCH(channel_names=CHANNEL_IDENTIFY)
class ZHAIdentifyButton(ZHAButton):
    """Defines a ZHA identify button."""

    @classmethod
    def create_entity(
        cls,
        unique_id: str,
        zha_device: ZhaDeviceType,
        channels: list[ChannelType],
        **kwargs,
    ) -> ZhaEntity | None:
        """Entity Factory.

        Return entity if it is a supported configuration, otherwise return None
        """
        if ZHA_ENTITIES.prevent_entity_creation(
            Platform.BUTTON, zha_device.ieee, CHANNEL_IDENTIFY
        ):
            return None
        return cls(unique_id, zha_device, channels, **kwargs)

    _attr_device_class: ButtonDeviceClass = ButtonDeviceClass.UPDATE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _command_name = "identify"

    def get_args(self) -> list[Any]:
        """Return the arguments to use in the command."""

        return [DEFAULT_DURATION]
