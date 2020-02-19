"""Support for Roku."""
import logging

from roku import Roku, RokuException
import voluptuous as vol

from homeassistant.const import CONF_HOST
from homeassistant.helpers import config_validation as cv

from .const import (
    DOMAIN,
    SERVICE_SCAN,
    CONF_DEVICES,
    DEFAULT_PORT,
    SUPPORTED_DOMAINS,
    ATTR_ROKU,
    DATA_ROKU,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            cv.ensure_list, [vol.Schema({vol.Required(CONF_HOST): cv.string})]
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Roku integration."""
    if DOMAIN in config:
        for entry_config in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": "import"}, data=entry_config
                )
            )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry for Roku."""
    hass.data.setdefault(DOMAIN, {})

    for domain in SUPPORTED_DOMAINS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, domain)
        )

    return True


async def async_unload_entry(hass, entry):
    """Unload Roku config entry."""
    for domain in SUPPORTED_DOMAINS:
        await hass.config_entries.async_forward_entry_unload(entry, domain)

    return True
