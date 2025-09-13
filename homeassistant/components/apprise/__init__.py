"""The apprise component."""

import apprise
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import CONF_FILE_URL, DATA_HASS_CONFIG, DEFAULT_NAME, DOMAIN

type AppriseConfigEntry = ConfigEntry[apprise.AppriseConfig]

PLATFORMS = [Platform.NOTIFY]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Optional(CONF_FILE_URL): cv.string,
                vol.Optional(CONF_URL): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Apprise component."""

    hass.data[DATA_HASS_CONFIG] = config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AppriseConfigEntry) -> bool:
    """Set up Apprise from a config entry."""

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data

    hass.async_create_task(
        discovery.async_load_platform(
            hass, Platform.NOTIFY, DOMAIN, dict(entry.data), hass.data[DATA_HASS_CONFIG]
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AppriseConfigEntry) -> bool:
    """Unload a Apprise config entry."""
    return True
