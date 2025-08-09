"""The songpal component."""

import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ENDPOINT, DOMAIN
from .coordinator import SongpalConfigEntry, SongpalCoordinator

_LOGGER = logging.getLogger(__name__)

SONGPAL_CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(CONF_NAME): cv.string, vol.Required(CONF_ENDPOINT): cv.string}
)

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): vol.All(cv.ensure_list, [SONGPAL_CONFIG_SCHEMA])},
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.NUMBER,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up songpal environment."""
    if (conf := config.get(DOMAIN)) is None:
        return True
    for config_entry in conf:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config_entry,
            ),
        )
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SongpalConfigEntry,
) -> bool:
    """Set up songpal coordinator and entities."""

    coordinator = SongpalCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    if not coordinator.initialized:
        _LOGGER.warning("Songpal coordinator not initialised")
        raise ConfigEntryNotReady

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SongpalConfigEntry) -> bool:
    """Unload songpal media player."""
    await entry.runtime_data.destroy()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
