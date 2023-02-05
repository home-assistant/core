"""Component to embed Google Cast."""
from __future__ import annotations

import logging
from typing import Protocol

from pychromecast import Chromecast
import voluptuous as vol

from homeassistant.components.media_player import BrowseMedia, MediaType
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)
from homeassistant.helpers.typing import ConfigType

from . import home_assistant_cast
from .const import DOMAIN
from .media_player import ENTITY_SCHEMA

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Cast component."""
    if (conf := config.get(DOMAIN)) is not None:
        media_player_config_validated = []
        media_player_config = conf.get("media_player", {})
        if not isinstance(media_player_config, list):
            media_player_config = [media_player_config]
        for cfg in media_player_config:
            try:
                cfg = ENTITY_SCHEMA(cfg)
                media_player_config_validated.append(cfg)
            except vol.Error as ex:
                _LOGGER.warning("Invalid config '%s': %s", cfg, ex)

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=media_player_config_validated,
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cast from a config entry."""
    await home_assistant_cast.async_setup_ha_cast(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    hass.data[DOMAIN] = {"cast_platform": {}, "unknown_models": {}}
    await async_process_integration_platforms(hass, DOMAIN, _register_cast_platform)
    return True


class CastProtocol(Protocol):
    """Define the format of cast platforms."""

    async def async_get_media_browser_root_object(
        self, hass: HomeAssistant, cast_type: str
    ) -> list[BrowseMedia]:
        """Create a list of root objects for media browsing."""

    async def async_browse_media(
        self,
        hass: HomeAssistant,
        media_content_type: MediaType | str,
        media_content_id: str,
        cast_type: str,
    ) -> BrowseMedia | None:
        """Browse media.

        Return a BrowseMedia object or None if the media does not belong to
        this platform.
        """

    async def async_play_media(
        self,
        hass: HomeAssistant,
        cast_entity_id: str,
        chromecast: Chromecast,
        media_type: MediaType | str,
        media_id: str,
    ) -> bool:
        """Play media.

        Return True if the media is played by the platform, False if not.
        """


async def _register_cast_platform(
    hass: HomeAssistant, integration_domain: str, platform: CastProtocol
):
    """Register a cast platform."""
    if (
        not hasattr(platform, "async_get_media_browser_root_object")
        or not hasattr(platform, "async_browse_media")
        or not hasattr(platform, "async_play_media")
    ):
        raise HomeAssistantError(f"Invalid cast platform {platform}")
    hass.data[DOMAIN]["cast_platform"][integration_domain] = platform


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove Home Assistant Cast user."""
    await home_assistant_cast.async_remove_user(hass, entry)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Remove cast config entry from a device.

    The actual cleanup is done in CastMediaPlayerEntity.async_will_remove_from_hass.
    """
    return True
