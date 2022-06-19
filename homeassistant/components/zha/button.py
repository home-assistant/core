"""Support for ZHA button."""
from __future__ import annotations

import abc
import functools
import logging
from typing import Any

import zigpy.exceptions
from zigpy.zcl.foundation import Status

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
CONFIG_DIAGNOSTIC_MATCH = functools.partial(
    ZHA_ENTITIES.config_diagnostic_match, Platform.BUTTON
)
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


class ZHAAttributeButton(ZhaEntity, ButtonEntity):
    """Defines a ZHA button, which stes value to an attribute."""

    _attribute_name: str = None
    _attribute_value: Any = None

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

    async def async_press(self) -> None:
        """Write attribute with defined value."""
        try:
            result = await self._channel.cluster.write_attributes(
                {self._attribute_name: self._attribute_value}
            )
        except zigpy.exceptions.ZigbeeException as ex:
            self.error("Could not set value: %s", ex)
            return
        if not isinstance(result, Exception) and all(
            record.status == Status.SUCCESS for record in result[0]
        ):
            self.async_write_ha_state()


@CONFIG_DIAGNOSTIC_MATCH(
    channel_names="tuya_manufacturer",
    manufacturers={
        "_TZE200_htnnfasr",
    },
)
class FrostLockResetButton(ZHAAttributeButton, id_suffix="reset_frost_lock"):
    """Defines a ZHA identify button."""

    _attribute_name = "frost_lock_reset"
    _attribute_value = 0
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG
