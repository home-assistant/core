"""Support for EnOcean Cover module."""

from typing import Any

from enocean.utils import combine_hex
import voluptuous as vol

from homeassistant.components.cover import ATTR_POSITION, PLATFORM_SCHEMA, CoverEntity
from homeassistant.const import CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .device import EnOceanEntity

CONF_CHANNEL = "channel"
DEFAULT_NAME = "EnOcean Cover"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the EnOcean cover platform."""
    dev_id: list[int] = config[CONF_ID]
    dev_name: str = config[CONF_NAME]

    add_entities([EnOceanCover(dev_id, dev_name)])


class EnOceanCover(EnOceanEntity, CoverEntity):
    """Representation of an EnOcean cover device."""

    def __init__(self, dev_id: list[int], dev_name: str) -> None:
        """Initialize the EnOcean cover device."""
        super().__init__(dev_id)
        self._attr_position: int | None = None
        self._attr_unique_id = str(combine_hex(dev_id))
        self._attr_name = dev_name

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self._attr_position is None:
            return None
        if self._attr_position > 0:
            return False
        return True

    def value_changed(self, packet: Any) -> None:
        """Update the internal state of the cover when a packet arrives."""
        self._attr_position = int(packet.data[1])
        self.schedule_update_ha_state()

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position.

        Avoid calibration error.
        """
        if self._attr_position is not None:
            if self._attr_position <= 5:
                return 0
            if self._attr_position >= 95:
                return 100
            return self._attr_position

        # ___ Force the device to reply its position.
        # ___ The device will resend a message with its position.
        optional = [
            0x03,
        ]
        optional.extend(self.dev_id)
        optional.extend([0xFF, 0x00])
        self.send_command(
            data=[0xD2, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00],
            optional=optional,
            packet_type=0x01,
        )
        return None

    def open_cover(self, **kwargs: Any) -> None:
        """Move the roller shutter up."""

        # ___ The new position value will be 100.
        # ___ Send the command to set a new position.
        optional = [
            0x03,
        ]
        optional.extend(self.dev_id)
        optional.extend([0xFF, 0x00])
        self.send_command(
            data=[0xD2, 0x64, 0x7F, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00],
            optional=optional,
            packet_type=0x01,
        )

    def close_cover(self, **kwargs: Any) -> None:
        """Move the roller shutter down."""

        # ___ The new position value will be 0.
        # ___ Send the command to set a new position.
        optional = [
            0x03,
        ]
        optional.extend(self.dev_id)
        optional.extend([0xFF, 0x00])
        self.send_command(
            data=[0xD2, 0x00, 0x7F, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00],
            optional=optional,
            packet_type=0x01,
        )

    def set_cover_position(self, **kwargs: Any) -> None:
        """Move the roller shutter to a specific position."""
        # ___ Send the command to set a new position.
        newVal: int = int(kwargs[ATTR_POSITION])
        optional = [
            0x03,
        ]
        optional.extend(self.dev_id)
        optional.extend([0xFF, 0x00])

        self.send_command(
            data=[
                0xD2,
                newVal,
                0x7F,
                0x00,
                0x01,
                0x00,
                0x00,
                0x00,
                0x00,
                0x00,
            ],
            optional=optional,
            packet_type=0x01,
        )

    def stop_cover(self, **kwargs: Any) -> None:
        """Stop the roller shutter."""
        # ___ Send the stop command
        optional = [
            0x03,
        ]
        optional.extend(self.dev_id)
        optional.extend([0xFF, 0x00])
        self.send_command(
            data=[0xD2, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00],
            optional=optional,
            packet_type=0x01,
        )
