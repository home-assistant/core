"""Support for interfacing with Russound via RNET Protocol."""

from __future__ import annotations

import logging
import math

from russound import russound
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_ZONES = "zones"
CONF_SOURCES = "sources"


ZONE_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})

SOURCE_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_ZONES): vol.Schema({cv.positive_int: ZONE_SCHEMA}),
        vol.Required(CONF_SOURCES): vol.All(cv.ensure_list, [SOURCE_SCHEMA]),
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Russound RNET platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    if host is None or port is None:
        _LOGGER.error("Invalid config. Expected %s and %s", CONF_HOST, CONF_PORT)
        return

    russ = russound.Russound(host, port)
    russ.connect()

    sources = [source["name"] for source in config[CONF_SOURCES]]

    if russ.is_connected():
        for zone_id, extra in config[CONF_ZONES].items():
            add_entities(
                [RussoundRNETDevice(hass, russ, sources, zone_id, extra)], True
            )
    else:
        _LOGGER.error("Not connected to %s:%s", host, port)


class RussoundRNETDevice(MediaPlayerEntity):
    """Representation of a Russound RNET device."""

    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, hass, russ, sources, zone_id, extra):
        """Initialise the Russound RNET device."""
        self._attr_name = extra["name"]
        self._russ = russ
        self._attr_source_list = sources
        # Each controller has a maximum of 6 zones, every increment of 6 zones
        # maps to an additional controller for easier backward compatibility
        self._controller_id = str(math.ceil(zone_id / 6))
        # Each zone resets to 1-6 per controller
        self._zone_id = (zone_id - 1) % 6 + 1

    def update(self) -> None:
        """Retrieve latest state."""
        # Updated this function to make a single call to get_zone_info, so that
        # with a single call we can get On/Off, Volume and Source, reducing the
        # amount of traffic and speeding up the update process.
        try:
            ret = self._russ.get_zone_info(self._controller_id, self._zone_id, 4)
        except BrokenPipeError:
            _LOGGER.error("Broken Pipe Error, trying to reconnect to Russound RNET")
            self._russ.connect()
            ret = self._russ.get_zone_info(self._controller_id, self._zone_id, 4)

        _LOGGER.debug("ret= %s", ret)
        if ret is not None:
            _LOGGER.debug(
                "Updating status for RNET zone %s on controller %s",
                self._zone_id,
                self._controller_id,
            )
            if ret[0] == 0:
                self._attr_state = MediaPlayerState.OFF
            else:
                self._attr_state = MediaPlayerState.ON
            self._attr_volume_level = ret[2] * 2 / 100.0
            # Returns 0 based index for source.
            index = ret[1]
            # Possibility exists that user has defined list of all sources.
            # If a source is set externally that is beyond the defined list then
            # an exception will be thrown.
            # In this case return and unknown source (None)
            if self.source_list and 0 <= index < len(self.source_list):
                self._attr_source = self.source_list[index]
        else:
            _LOGGER.error("Could not update status for zone %s", self._zone_id)

    def set_volume_level(self, volume: float) -> None:
        """Set volume level.  Volume has a range (0..1).

        Translate this to a range of (0..100) as expected
        by _russ.set_volume()
        """
        self._russ.set_volume(self._controller_id, self._zone_id, volume * 100)

    def turn_on(self) -> None:
        """Turn the media player on."""
        self._russ.set_power(self._controller_id, self._zone_id, "1")

    def turn_off(self) -> None:
        """Turn off media player."""
        self._russ.set_power(self._controller_id, self._zone_id, "0")

    def mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        self._russ.toggle_mute(self._controller_id, self._zone_id)

    def select_source(self, source: str) -> None:
        """Set the input source."""
        if self.source_list and source in self.source_list:
            index = self.source_list.index(source)
            # 0 based value for source
            self._russ.set_source(self._controller_id, self._zone_id, index)
