"""Decorator service for the media_player.play_media service."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Media Extractor from a config entry."""

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the media extractor service."""

    async_setup_services(hass)

    return True
