"""Media player platform for Sony Projector power control."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA as MEDIA_PLAYER_PLATFORM_SCHEMA,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import SonyProjectorConfigEntry
from .client import ProjectorClient, ProjectorClientError
from .const import CONF_TITLE, DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = MEDIA_PLAYER_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import YAML configuration and instruct the user to migrate."""

    _LOGGER.warning(
        "YAML support for sony_projector media players is deprecated and will be "
        "imported into a config entry. Please remove it from configuration.yaml"
    )

    host = config.get(CONF_HOST)
    if not host:
        _LOGGER.error("Missing 'host' in sony_projector configuration; skipping import")
        return

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_HOST: host,
                CONF_NAME: config.get(CONF_NAME),
            },
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SonyProjectorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up media player entities from a config entry."""

    runtime_data = entry.runtime_data
    async_add_entities([SonyProjectorMediaPlayer(entry, runtime_data.client)])


class SonyProjectorMediaPlayer(MediaPlayerEntity):
    """Representation of a Sony projector as a media player."""

    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
    )
    _attr_should_poll = True

    def __init__(
        self, entry: SonyProjectorConfigEntry, client: ProjectorClient
    ) -> None:
        """Initialize the media player entity."""

        self._entry = entry
        self._client = client
        self._identifier = entry.data[CONF_HOST]
        name = entry.data.get(CONF_TITLE, entry.title or DEFAULT_NAME)
        self._attr_name = name
        self._attr_unique_id = f"{self._identifier}-media_player"
        self._attr_available = False
        self._attr_state: MediaPlayerState | None = None
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._identifier)},
            "manufacturer": "Sony",
            "name": name,
        }

    async def async_update(self) -> None:
        """Fetch the latest state from the projector."""

        try:
            state = await self._client.async_get_state()
        except ProjectorClientError as err:
            _LOGGER.error(
                "Failed to query projector '%s' power state: %s",
                self._identifier,
                err,
            )
            self._attr_available = False
            self._attr_state = None
            return

        self._attr_available = True
        self._attr_state = MediaPlayerState.ON if state.is_on else MediaPlayerState.OFF

    async def async_turn_on(self) -> None:
        """Turn the projector on."""

        await self._async_set_power(True)

    async def async_turn_off(self) -> None:
        """Turn the projector off."""

        await self._async_set_power(False)

    async def _async_set_power(self, powered: bool) -> None:
        """Send a power command to the projector."""

        try:
            await self._client.async_set_power(powered)
        except ProjectorClientError as err:
            _LOGGER.error(
                "Failed to send power command to projector '%s': %s",
                self._identifier,
                err,
            )
            self._attr_available = False
            return

        self._attr_available = True
        self._attr_state = MediaPlayerState.ON if powered else MediaPlayerState.OFF
