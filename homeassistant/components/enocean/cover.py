"""Support for EnOcean roller shutters (EEP D2-05-00)."""
from __future__ import annotations

import logging

from enocean.protocol.packet import Packet  # pylint: disable=import-error
from enocean.utils import combine_hex  # pylint: disable=import-error
import voluptuous as vol  # pylint: disable=import-error

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASSES_SCHEMA,
    PLATFORM_SCHEMA,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.components.enocean.const import SIGNAL_SEND_MESSAGE
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .device import EnOceanEntity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "EnOcean roller shutter"
DEPENDENCIES = ["enocean"]

CONF_SENDER_ID = "sender_id"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Required(CONF_SENDER_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASSES_SCHEMA,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Binary Sensor platform for EnOcean."""
    dev_id = config.get(CONF_ID)
    sender_id = config.get(CONF_SENDER_ID)
    dev_name = config.get(CONF_NAME)
    device_class = config.get(CONF_DEVICE_CLASS)

    add_entities([EnOceanCover(sender_id, dev_id, dev_name, device_class)])


class EnOceanCover(EnOceanEntity, CoverEntity):
    """Representation of EnOcean Roller Shutter (EEP D2-05-00)."""

    def __init__(self, sender_id, dev_id, dev_name, device_class):
        """Initialize the EnOcean binary sensor."""
        super().__init__(dev_id, dev_name)
        self._device_class = device_class
        self.position = None
        self.closed = None
        self.sender_id = sender_id
        self._attr_unique_id = f"{combine_hex(dev_id)}-{device_class}"

        _LOGGER.debug("Init EnOcean Roller Shutter: %s", self._attr_unique_id)

    @property
    def name(self):
        """Return the default name for the binary sensor."""
        return self.dev_name

    @property
    def device_class(self):
        """Return the class of this sensor."""
        return self._device_class

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        flags = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )
        return flags

    @property
    def current_cover_position(self) -> int | None:
        """Return the current cover position."""
        return self.position

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening or not."""
        return False

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing or not."""
        return False

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        return self.closed

    def open_cover(self, **kwargs):
        """Open the cover."""
        telegram = [0xD2, 0, 0, 0, 1]
        telegram.extend(self.sender_id)
        telegram.extend([0x00])
        self.send_telegram(telegram, [], 0x01)

    def close_cover(self, **kwargs):
        """Close the cover."""
        telegram = [0xD2, 100, 0, 0, 1]
        telegram.extend(self.sender_id)
        telegram.extend([0x00])
        self.send_telegram(telegram, [], 0x01)

    def set_cover_position(self, **kwargs):
        """Set the cover position."""
        telegram = [0xD2, 100 - kwargs[ATTR_POSITION], 0, 0, 1]
        telegram.extend(self.sender_id)
        telegram.extend([0x00])
        self.send_telegram(telegram, [], 0x01)

    def stop_cover(self, **kwargs):
        """Stop any cover movement."""
        telegram = [0xD2, 2]
        telegram.extend(self.sender_id)
        telegram.extend([0x00])
        self.send_telegram(telegram, [], 0x01)

    def value_changed(self, packet):
        """Fire an event with the data that have changed.

        This method is called when there is an incoming packet associated
        with this platform.
        """

        # position is inversed in Home Assistant and in EnOcean:
        # 0 means 'closed' in Home Assistant and 'open' in EnOcean
        # 100 means 'open' in Home Assistant and 'closed' in EnOcean
        self.position = 100 - packet.data[1]
        if self.position == 100:
            self.closed = True
        else:
            self.closed = False

        self.schedule_update_ha_state()

    def send_telegram(self, data, optional, packet_type):
        """Send a telegram via the EnOcean dongle to only this device."""
        # optional contains: subtelegram 3, destination id, max dBm for sending and security level 0
        packet = Packet(
            packet_type, data=data, optional=[3] + self.dev_id + [0xFF] + [0]
        )
        dispatcher_send(self.hass, SIGNAL_SEND_MESSAGE, packet)
