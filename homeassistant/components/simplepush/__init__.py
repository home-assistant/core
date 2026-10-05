"""The simplepush component."""

from simplepush import Client

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import CONF_ENTRY, DATA_HASS_CONFIG, DOMAIN

PLATFORMS = [Platform.NOTIFY]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type SimplePushConfigEntry = ConfigEntry[Client]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the simplepush component."""

    hass.data[DATA_HASS_CONFIG] = config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: SimplePushConfigEntry) -> bool:
    """Set up simplepush from a config entry."""

    if CONF_API_TOKEN in entry.data:
        entry.runtime_data = Client(api_token=entry.data[CONF_API_TOKEN])
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Entries of the old app keep their legacy notify action, also after
    # they moved to the current app.
    if CONF_NAME in entry.data:
        hass.async_create_task(
            discovery.async_load_platform(
                hass,
                Platform.NOTIFY,
                DOMAIN,
                {**entry.data, CONF_ENTRY: entry},
                hass.data[DATA_HASS_CONFIG],
            )
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SimplePushConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
