"""Component to embed Google Cast."""

from __future__ import annotations

from typing import Protocol

from pychromecast import Chromecast

from homeassistant.components.media_player import BrowseMedia, MediaType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.integration_platform import (
    async_process_integration_platforms,
)

from . import home_assistant_cast
from .const import DOMAIN

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)
PLATFORMS = [Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cast from a config entry."""
    hass.data[DOMAIN] = {"cast_platform": {}, "unknown_models": {}}
    await home_assistant_cast.async_setup_ha_cast(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
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


@callback
def _register_cast_platform(
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
