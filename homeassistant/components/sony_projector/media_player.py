"""Media player platform for Sony Projector power control."""

from __future__ import annotations

import logging

import pysdcp
import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Sony Projector media player platform."""

    host = config[CONF_HOST]
    name = config[CONF_NAME]
    sdcp_connection = pysdcp.Projector(host)

    try:
        sdcp_connection.get_power()
    except ConnectionError:
        _LOGGER.error("Failed to connect to projector '%s'", host)
        return

    add_entities([SonyProjectorMediaPlayer(hass, sdcp_connection, name, host)], True)


class SonyProjectorMediaPlayer(MediaPlayerEntity):
    """Representation of a Sony projector as a media player."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        hass: HomeAssistant,
        sdcp_connection: pysdcp.Projector,
        name: str,
        host: str,
    ) -> None:
        """Initialize the media player entity."""

        self._hass = hass
        self._sdcp = sdcp_connection
        self._attr_name = name
        self._host = host
        self._state: MediaPlayerState | None = None
        self._attr_available = False
        self._attr_unique_id = f"{host}-media_player"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, host)},
            "manufacturer": "Sony",
            "name": name,
        }

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current power state."""

        return self._state

    async def async_update(self) -> None:
        """Fetch the latest state from the projector."""

        try:
            power_state = await self._hass.async_add_executor_job(self._sdcp.get_power)
        except ConnectionError as error:
            _LOGGER.error(
                "Failed to query projector '%s' power state: %s", self._host, error
            )
            self._attr_available = False
            self._state = None
            return

        self._attr_available = True
        self._state = MediaPlayerState.ON if power_state else MediaPlayerState.OFF

    async def async_turn_on(self) -> None:
        """Turn the projector on."""

        await self._async_set_power(True)

    async def async_turn_off(self) -> None:
        """Turn the projector off."""

        await self._async_set_power(False)

    async def _async_set_power(self, powered: bool) -> None:
        """Send a power command to the projector."""

        try:
            success = await self._hass.async_add_executor_job(
                self._sdcp.set_power, powered
            )
        except ConnectionError as error:
            _LOGGER.error(
                "Failed to send power command to projector '%s': %s", self._host, error
            )
            self._attr_available = False
            return

        if not success:
            _LOGGER.error(
                "Projector '%s' rejected power command (powered=%s)",
                self._host,
                powered,
            )
            return

        self._attr_available = True
        self._state = MediaPlayerState.ON if powered else MediaPlayerState.OFF
