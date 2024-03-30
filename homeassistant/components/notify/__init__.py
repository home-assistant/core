"""Provides functionality to notify people."""

from __future__ import annotations

import voluptuous as vol

import homeassistant.components.persistent_notification as pn
from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType

from .const import (  # noqa: F401
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_TITLE,
    DOMAIN,
    NOTIFY_SERVICE_SCHEMA,
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

    for setup in async_setup_legacy(hass, config):
        # Tasks are created as tracked tasks to ensure startup
        # waits for them to finish, but we explicitly do not
        # want to wait for them to finish here because we want
        # any config entries that use notify as a base platform
        # to be able to start with out having to wait for the
        # legacy platforms to finish setting up.
        hass.async_create_task(setup, eager_start=True)

    async def persistent_notification(service: ServiceCall) -> None:
        """Send notification via the built-in persistent_notify integration."""
        message: Template = service.data[ATTR_MESSAGE]
        message.hass = hass
        check_templates_warn(hass, message)

        title = None
        title_tpl: Template | None
        if title_tpl := service.data.get(ATTR_TITLE):
            check_templates_warn(hass, title_tpl)
            title_tpl.hass = hass
            title = title_tpl.async_render(parse_result=False)

        notification_id = None
        if data := service.data.get(ATTR_DATA):
            notification_id = data.get(pn.ATTR_NOTIFICATION_ID)

        pn.async_create(
            hass, message.async_render(parse_result=False), title, notification_id
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PERSISTENT_NOTIFICATION,
        persistent_notification,
        schema=NOTIFY_SERVICE_SCHEMA,
    )

    return True
