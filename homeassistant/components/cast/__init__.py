"""Component to embed Google Cast."""
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
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
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove Home Assistant Cast user."""
    await home_assistant_cast.async_remove_user(hass, entry)
