"""Component to embed Google Cast."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv

from . import home_assistant_cast
from .const import DOMAIN
from .media_player import ENTITY_SCHEMA

# Deprecated from 2021.4, remove in 2021.6
CONFIG_SCHEMA = cv.deprecated(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the Cast component."""
    conf = config.get(DOMAIN)

    if conf is not None:
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
                context={"source": config_entries.SOURCE_IMPORT},
                data=media_player_config_validated,
            )
        )

    return True


async def async_setup_entry(hass, entry: config_entries.ConfigEntry):
    """Set up Cast from a config entry."""
    await home_assistant_cast.async_setup_ha_cast(hass, entry)

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "media_player")
    )
    return True


async def async_remove_entry(hass, entry):
    """Remove Home Assistant Cast user."""
    await home_assistant_cast.async_remove_user(hass, entry)
