"""Provides functionality to notify people."""
from __future__ import annotations

from functools import partial
from typing import Any

import voluptuous as vol

import homeassistant.components.persistent_notification as pn
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.service_integration import ServiceIntegration
from homeassistant.helpers.service_platform import PlatformService, ServiceDescription
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_TITLE,
    DOMAIN,
    LOGGER,
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

    service_integration = hass.data[DOMAIN] = ServiceIntegration(
        hass, LOGGER, DOMAIN, config
    )
    await service_integration.async_setup()

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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    service_integration: ServiceIntegration = hass.data[DOMAIN]
    return await service_integration.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    service_integration: ServiceIntegration = hass.data[DOMAIN]
    return await service_integration.async_unload_entry(entry)


class NotifyService(PlatformService):
    """Represent a notify platform service."""

    @property
    def service_name(self) -> str:
        """Return the name of the service, not including domain."""
        return f"{self.platform.platform_name}_{SERVICE_NOTIFY}"

    @property
    def service_description(self) -> ServiceDescription:
        """Return the service description."""
        service_name = self.service_name
        return ServiceDescription(
            SERVICE_NOTIFY,
            service_name,
            f"Send a notification with {service_name}",
            f"Sends a notification message using the {service_name} service.",
        )

    @property
    def service_schema(self) -> vol.Schema:
        """Return the service schema."""
        return NOTIFY_SERVICE_SCHEMA

    def send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message.

        kwargs can contain ATTR_TITLE to specify a title.
        """
        raise NotImplementedError()

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message.

        kwargs can contain ATTR_TITLE to specify a title.
        """
        await self.hass.async_add_executor_job(
            partial(self.send_message, message, **kwargs)
        )

    async def async_handle_service(self, service_call: ServiceCall) -> None:
        """Handle the service call."""
        kwargs = {}
        message = service_call.data[ATTR_MESSAGE]
        check_templates_warn(self.hass, message)
        message.hass = self.hass
        kwargs[ATTR_MESSAGE] = message.async_render(parse_result=False)

        if title := service_call.data.get(ATTR_TITLE):
            check_templates_warn(self.hass, title)
            title.hass = self.hass
            kwargs[ATTR_TITLE] = title.async_render(parse_result=False)

        if (target := service_call.data.get(ATTR_TARGET)) is not None:
            kwargs[ATTR_TARGET] = target

        if data := service_call.data.get(ATTR_DATA):
            kwargs[ATTR_DATA] = data

        await self.async_send_message(**kwargs)
