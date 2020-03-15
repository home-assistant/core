"""The sentry integration."""
import logging

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import __version__
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import CONF_DSN, CONF_ENVIRONMENT, DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {vol.Required(CONF_DSN): cv.string, CONF_ENVIRONMENT: cv.string}
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Sentry component."""
    conf = config.get(DOMAIN)
    if conf is not None:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Sentry from a config entry."""
    conf = entry.data

    hass.data[DOMAIN] = conf

    # https://docs.sentry.io/platforms/python/logging/
    sentry_logging = LoggingIntegration(
        level=logging.INFO,  # Capture info and above as breadcrumbs
        event_level=logging.ERROR,  # Send errors as events
    )

    sentry_sdk.init(
        dsn=conf.get(CONF_DSN),
        environment=conf.get(CONF_ENVIRONMENT),
        integrations=[sentry_logging],
        release=f"homeassistant-{__version__}",
    )

    return True
