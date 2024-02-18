"""Set up the smtp component."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PORT,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_TIMEOUT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_DEBUG,
    CONF_ENCRYPTION,
    CONF_SENDER_NAME,
    CONF_SERVER,
    DEFAULT_DEBUG,
    DEFAULT_ENCRYPTION,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    ENCRYPTION_OPTIONS,
)
from .notify import MailNotificationService

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RECIPIENT): vol.All(cv.ensure_list, [vol.Email()]),
        vol.Required(CONF_SENDER): vol.Email(),
        vol.Optional(CONF_SERVER, default=DEFAULT_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_ENCRYPTION, default=DEFAULT_ENCRYPTION): vol.In(
            ENCRYPTION_OPTIONS
        ),
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_SENDER_NAME): cv.string,
        vol.Optional(CONF_DEBUG, default=DEFAULT_DEBUG): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)


PLATFORMS = [Platform.NOTIFY]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the SMTP notify component from configuration.yaml."""
    hass.data.setdefault(DOMAIN, {})["hass_config"] = config
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up SMTP config entry."""
    hass_config: ConfigType = hass.data[DOMAIN]["hass_config"]
    hass.data[DOMAIN][config_entry.entry_id] = None
    config = dict(config_entry.data) | {"entry_id": config_entry.entry_id}
    hass.async_create_task(
        discovery.async_load_platform(
            hass, Platform.NOTIFY.value, DOMAIN, config, hass_config
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload SMTP config entry."""
    mail_service: MailNotificationService | None = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    if mail_service is not None:
        await mail_service.async_unregister_services()
    return True
