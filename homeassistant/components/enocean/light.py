"""Support for EnOcean light sources."""

from __future__ import annotations

import math
from typing import Any

from enocean.protocol.packet import Packet
import voluptuous as vol

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA,
    ColorMode,
    LightEntity,
)
from homeassistant.const import CONF_ID, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .config_entry import EnOceanConfigEntry
from .config_flow import CONF_ENOCEAN_DEVICE_TYPE_ID, CONF_ENOCEAN_DEVICES
from .enocean_id import EnOceanID
from .entity import EnOceanEntity
from .importer import (
    EnOceanPlatformConfig,
    register_platform_config_for_migration_to_config_entry,
)
from .supported_device_type import (
    EnOceanSupportedDeviceType,
    get_supported_enocean_device_types,
)

CONF_SENDER_ID = "sender_id"

DEFAULT_NAME = ""

PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_ID, default=[]): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Required(CONF_SENDER_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the EnOcean light platform."""
    register_platform_config_for_migration_to_config_entry(
        EnOceanPlatformConfig(platform=Platform.LIGHT, config=config)
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""
    devices = entry.options.get(CONF_ENOCEAN_DEVICES, [])

    for device in devices:
        device_type_id = device[CONF_ENOCEAN_DEVICE_TYPE_ID]
        device_type = get_supported_enocean_device_types()[device_type_id]

        if device_type.unique_id == "Eltako_FUD61NPN":
            device_id = EnOceanID(device["id"])
            sender_id = EnOceanID(0)
            if device["sender_id"] != "":
                sender_id = EnOceanID(device["sender_id"])

            async_add_entities(
                [
                    EnOceanLight(
                        sender_id=sender_id,
                        dev_name=device["name"],
                        dev_id=device_id,
                        dev_type=device_type,
                        gateway_id=entry.runtime_data.gateway.chip_id,
                    )
                ]
            )


class EnOceanLight(EnOceanEntity, LightEntity):
    """Representation of an EnOcean light source."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_brightness: int | None = None
    _attr_is_on = False

    def __init__(
        self,
        sender_id: EnOceanID,
        dev_id: EnOceanID,
        gateway_id: EnOceanID,
        dev_name: str,
        dev_type: EnOceanSupportedDeviceType = EnOceanSupportedDeviceType(),
        name: str | None = None,
    ) -> None:
        """Initialize the EnOcean light source."""
        super().__init__(
            enocean_device_id=dev_id,
            enocean_gateway_id=gateway_id,
            device_name=dev_name,
            name=name,
            dev_type=dev_type,
        )
        self._attr_is_on = False
        self._attr_brightness = None
        self._sender_id = sender_id
        self._attr_should_poll = False

    @property
    def brightness(self) -> int | None:
        """Brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._attr_brightness

    @property
    def is_on(self) -> bool | None:
        """If light is on."""
        return self._attr_is_on

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the light source on or sets a specific dimmer value."""
        if (brightness := kwargs.get(ATTR_BRIGHTNESS)) is not None:
            self._attr_brightness = brightness

        if self._attr_brightness is None:
            self._attr_brightness = 255
        bval = math.floor(self._attr_brightness / 256.0 * 100.0)
        if bval == 0:
            bval = 1
        command = [0xA5, 0x02, bval, 0x01, 0x09]
        command.extend(self._sender_id.to_bytelist())
        command.extend([0x00])
        self.send_command(command, [], 0x01)
        self._attr_is_on = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the light source off."""
        command = [0xA5, 0x02, 0x00, 0x01, 0x09]
        command.extend(self._sender_id.to_bytelist())
        command.extend([0x00])
        self.send_command(command, [], 0x01)
        self._attr_is_on = False

    def value_changed(self, packet: Packet) -> None:
        """Update the internal state of this device.

        Dimmer devices like Eltako FUD61 send telegram in different RORGs.
        We only care about the 4BS (0xA5).
        """
        if packet.data[0] == 0xA5 and packet.data[1] == 0x02:
            # _LOGGER.info("Received light packet: %s", packet)
            val = packet.data[2]
            self._attr_brightness = math.floor(val / 100.0 * 256.0)
            self._attr_is_on = bool(val != 0)
            # _LOGGER.info("Setting state to %s", self._attr_is_on)
            self.schedule_update_ha_state()
