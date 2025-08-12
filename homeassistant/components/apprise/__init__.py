"""The apprise component."""

import apprise

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .config_flow import validate_apprise_connection
from .const import DATA_HASS_CONFIG, DOMAIN

type AppriseConfigEntry = ConfigEntry[apprise.AppriseConfig]

PLATFORMS = [Platform.NOTIFY]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Apprise component."""

    hass.data[DATA_HASS_CONFIG] = config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AppriseConfigEntry) -> bool:
    """Set up Apprise from a config entry."""

    conf = dict(entry.data)

    if not await validate_apprise_connection(hass, conf):
        return False

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
