"""The telegram component."""

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PLATFORM, CONF_SOURCE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .notify import CONF_CHAT_ID

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Pass notify platform config from configuration.yaml to config flow for import."""

    # Handle scenario where there's no notifiers in configuration.yaml
    if Platform.NOTIFY not in config:
        return True

    for notify in config[Platform.NOTIFY]:
        if notify[CONF_PLATFORM] == DOMAIN:  # Only import Telegram notifiers
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={CONF_SOURCE: SOURCE_IMPORT},
                    data={
                        CONF_NAME: notify[CONF_NAME],
                        CONF_CHAT_ID: notify[CONF_CHAT_ID],
                    },
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up notifier from a config entry."""

    await discovery.async_load_platform(
        hass,
        Platform.NOTIFY,
        DOMAIN,
        {
            CONF_NAME: entry.data[CONF_NAME],
            CONF_CHAT_ID: entry.data[CONF_CHAT_ID],
        },
        {},
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the notifier."""
    hass.services.async_remove(Platform.NOTIFY, entry.data[CONF_NAME])
    return True
