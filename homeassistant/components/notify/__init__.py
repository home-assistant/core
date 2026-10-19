"""Provides functionality to notify people."""

from datetime import timedelta
import logging

import probatio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_RECIPIENTS,
    ATTR_TARGET,
    ATTR_TITLE,
    DATA_COMPONENT,
    DOMAIN,
    NOTIFY_SERVICE_SCHEMA,
    SERVICE_NOTIFY,
    SERVICE_PERSISTENT_NOTIFICATION,
    SERVICE_SEND_MESSAGE,
    NotifyEntityFeature,
)
from .entity import NotifyEntity, NotifyEntityDescription
from .legacy import (
    BaseNotificationService,
    async_reload,
    async_reset_platform,
    async_setup_legacy,
)
from .repairs import migrate_notify_issue
from .services import async_setup_services

# mypy: disallow-any-generics

# Platform specific data
ATTR_TITLE_DEFAULT = "Home Assistant"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_PLATFORM): cv.string,
        probatio.Optional(CONF_NAME): cv.string,
    },
    extra=probatio.ALLOW_EXTRA,
)

__all__ = [
    "ATTR_DATA",
    "ATTR_MESSAGE",
    "ATTR_RECIPIENTS",
    "ATTR_TARGET",
    "ATTR_TITLE",
    "ATTR_TITLE_DEFAULT",
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "NOTIFY_SERVICE_SCHEMA",
    "PLATFORM_SCHEMA",
    "SERVICE_NOTIFY",
    "SERVICE_PERSISTENT_NOTIFICATION",
    "SERVICE_SEND_MESSAGE",
    "BaseNotificationService",
    "NotifyEntity",
    "NotifyEntityDescription",
    "NotifyEntityFeature",
    "async_reload",
    "async_reset_platform",
    "migrate_notify_issue",
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the notify services."""

    for setup in async_setup_legacy(hass, config):
        # Tasks are created as tracked tasks to ensure startup
        # waits for them to finish, but we explicitly do not
        # want to wait for them to finish here because we want
        # any config entries that use notify as a base platform
        # to be able to start with out having to wait for the
        # legacy platforms to finish setting up.
        hass.async_create_task(setup, eager_start=True)

    # Reloading legacy platforms runs async_setup again; keep the existing
    # component so config entry entities stay tracked.
    if DATA_COMPONENT in hass.data:
        return True

    hass.data[DATA_COMPONENT] = EntityComponent[NotifyEntity](_LOGGER, DOMAIN, hass)
    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)
