"""The html5 component."""
import logging

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PLATFORM, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .issues import create_issue

_LOGGER = logging.getLogger(__name__)

PLATFORM = Platform.NOTIFY
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HTML5 push notification component."""
    existing_config_entry = hass.config_entries.async_entries(DOMAIN)
    # Iterate all entries for notify to only get HTML5
    if Platform.NOTIFY in config:
        for entry in config[Platform.NOTIFY]:
            if entry[CONF_PLATFORM] == DOMAIN:
                # the configuration has already been imported
                # but the YAML configuration is still present
                if existing_config_entry:
                    create_issue(hass, True)
                    return True
                hass.async_create_task(
                    hass.config_entries.flow.async_init(
                        DOMAIN, context={"source": SOURCE_IMPORT}, data=entry
                    )
                )
                return True

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HTML5 from a config entry."""
    hass.async_create_task(
        discovery.async_load_platform(
            hass, Platform.NOTIFY, DOMAIN, dict(entry.data), {}
        )
    )
    return True
