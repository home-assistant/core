"""Provides functionality to notify people."""
from __future__ import annotations

import voluptuous as vol

import homeassistant.components.persistent_notification as pn
from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (  # noqa: F401
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_TITLE,
    DOMAIN,
    NOTIFY_SERVICE_SCHEMA,
    PERSISTENT_NOTIFICATION_SERVICE_SCHEMA,
    SERVICE_NOTIFY,
    SERVICE_PERSISTENT_NOTIFICATION,
)
from .legacy import (  # noqa: F401
    BaseNotificationService,
    async_reload,
    async_reset_platform,
    async_setup_legacy,
    check_templates_warn,
)

# Platform specific data
ATTR_TITLE_DEFAULT = "Home Assistant"

PLATFORM_SCHEMA = vol.Schema(
    {vol.Required(CONF_PLATFORM): cv.string, vol.Optional(CONF_NAME): cv.string},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the notify services."""
    await async_setup_legacy(hass, config)

    async def persistent_notification(service: ServiceCall) -> None:
        """Send notification via the built-in persistsent_notify integration."""
        message = service.data[ATTR_MESSAGE]
        message.hass = hass
        check_templates_warn(hass, message)

        title = None
        if title_tpl := service.data.get(ATTR_TITLE):
            check_templates_warn(hass, title_tpl)
            title_tpl.hass = hass
            title = title_tpl.async_render(parse_result=False)

        pn.async_create(hass, message.async_render(parse_result=False), title)

    hass.services.async_register(
        DOMAIN,
        SERVICE_PERSISTENT_NOTIFICATION,
        persistent_notification,
        schema=PERSISTENT_NOTIFICATION_SERVICE_SCHEMA,
    )

    return True
