"""Support for Vera devices."""
import logging

from requests.exceptions import RequestException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EXCLUDE, CONF_LIGHTS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .common import (
    get_configured_platforms,
    get_controller_data_by_config,
    initialize_controller,
    set_controller_data,
)
from .const import CONF_CONTROLLER, DOMAIN

_LOGGER = logging.getLogger(__name__)

VERA_CONTROLLER = "vera_controller"

VERA_ID_LIST_SCHEMA = vol.Schema([int])

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CONTROLLER): cv.url,
                vol.Optional(CONF_EXCLUDE, default=[]): VERA_ID_LIST_SCHEMA,
                vol.Optional(CONF_LIGHTS, default=[]): VERA_ID_LIST_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, base_config: dict) -> bool:
    """Set up for Vera controllers."""
    config = base_config.get(DOMAIN, [])

    # Normalize the base url.
    config[CONF_CONTROLLER] = config.get(CONF_CONTROLLER).rstrip("/")

    # Build a map of already configured controllers.
    base_url_entries_map = {}
    for config_entry in hass.config_entries.async_entries(DOMAIN):
        base_url = config_entry.data.get(CONF_CONTROLLER)
        base_url_entries_map[base_url] = config_entry

    base_url = config.get(CONF_CONTROLLER)

    entry = base_url_entries_map.get(base_url)
    if entry:
        _LOGGER.debug("Updating existing config for %s", base_url)
        hass.config_entries.async_update_entry(entry=entry, data=config)
        return True

    _LOGGER.debug("Creating new config for %s", base_url)
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=config,
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Do setup of vera."""
    try:
        controller_data = initialize_controller(hass, config_entry.data)
    except RequestException:
        # There was a network related error connecting to the Vera controller.
        _LOGGER.exception("Error communicating with Vera API")
        return False

    set_controller_data(hass, controller_data)

    # Forward the config data to the necessary platforms.
    for platform in get_configured_platforms(controller_data):
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload Withings config entry."""
    controller_data = get_controller_data_by_config(hass=hass, entry=config_entry)

    if not controller_data:
        return True

    for platform in get_configured_platforms(controller_data):
        hass.async_create_task(
            hass.config_entries.async_forward_entry_unload(config_entry, platform)
        )

    return True
