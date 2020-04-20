"""The linky component."""
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType

from .const import DEFAULT_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)

ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [ACCOUNT_SCHEMA]))},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up Linky sensors from legacy config file."""

    conf = config.get(DOMAIN)
    if conf is None:
        return True

    for linky_account_conf in conf:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=linky_account_conf.copy(),
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Linky sensors."""
    # For backwards compat
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(
            entry, unique_id=entry.data[CONF_USERNAME]
        )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload Linky sensors."""
    return await hass.config_entries.async_forward_entry_unload(entry, "sensor")
