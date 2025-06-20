"""Add support for the Xiaomi TVs."""

from __future__ import annotations

import logging

import pymitv
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

DEFAULT_NAME = "Xiaomi TV"

_LOGGER = logging.getLogger(__name__)

# No host is needed for configuration, however it can be set.
PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Xiaomi TV platform."""

    # If a hostname is set. Discovery is skipped.
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)

    if host is not None:
        # Check if there's a valid TV at the IP address.
        if not pymitv.Discover().check_ip(host):
            _LOGGER.error("Could not find Xiaomi TV with specified IP: %s", host)
        else:
            # Register TV with Home Assistant.
            add_entities([XiaomiTV(host, name)])
    else:
        # Otherwise, discover TVs on network.
        add_entities(XiaomiTV(tv, DEFAULT_NAME) for tv in pymitv.Discover().scan())


class XiaomiTV(MediaPlayerEntity):
    """Represent the Xiaomi TV for Home Assistant."""

    _attr_assumed_state = True
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
    )

    def __init__(self, ip, name):
        """Receive IP address and name to construct class."""

        # Initialize the Xiaomi TV.
        self._tv = pymitv.TV(ip)
        # Default name value, only to be overridden by user.
        self._attr_name = name
        self._attr_state = MediaPlayerState.OFF

    def turn_off(self) -> None:
        """Instruct the TV to turn sleep.

        This is done instead of turning off,
        because the TV won't accept any input when turned off. Thus, the user
        would be unable to turn the TV back on, unless it's done manually.
        """
        if self.state != MediaPlayerState.OFF:
            self._tv.sleep()

            self._attr_state = MediaPlayerState.OFF

    def turn_on(self) -> None:
        """Wake the TV back up from sleep."""
        if self.state != MediaPlayerState.ON:
            self._tv.wake()

            self._attr_state = MediaPlayerState.ON

    def volume_up(self) -> None:
        """Increase volume by one."""
        self._tv.volume_up()

    def volume_down(self) -> None:
        """Decrease volume by one."""
        self._tv.volume_down()
