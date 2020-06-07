"""The dlna_dmr component."""
from collections import OrderedDict
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DLNA_DMR_CONFIG_SCHEMA = vol.Schema({vol.Required(CONF_URL): cv.string})

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): vol.All(cv.ensure_list, [DLNA_DMR_CONFIG_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: OrderedDict) -> bool:
    """Set up DLNA DMR environment."""
    conf = config.get(DOMAIN)
    if conf is None:
        return True
    for config_entry in conf:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config_entry,
            ),
        )
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up DLNA DMR media player."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "media_player")
    )
    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Unload DLNA DMR media player."""
    return await hass.config_entries.async_forward_entry_unload(entry, "media_player")
