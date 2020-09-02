"""Provides functionality to notify people."""
import asyncio
from dataclasses import dataclass
from functools import partial
import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_per_platform, discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.loader import bind_hass
from homeassistant.setup import async_prepare_setup_platform
from homeassistant.util import slugify

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

# Platform specific data
ATTR_DATA = "data"

# Text to notify user of
ATTR_MESSAGE = "message"

# Target of the notification (user, device, etc)
ATTR_TARGET = "target"

# Title of notification
ATTR_TITLE = "title"
ATTR_TITLE_DEFAULT = "Home Assistant"

DOMAIN = "notify"

SERVICE_NOTIFY = "notify"

NOTIFY_SERVICES = "notify_services"

PLATFORM_SCHEMA = vol.Schema(
    {vol.Required(CONF_PLATFORM): cv.string, vol.Optional(CONF_NAME): cv.string},
    extra=vol.ALLOW_EXTRA,
)

NOTIFY_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MESSAGE): cv.template,
        vol.Optional(ATTR_TITLE): cv.template,
        vol.Optional(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_DATA): dict,
    }
)


@bind_hass
async def async_reload(hass: HomeAssistantType, integration_name: str) -> None:
    """Register notify services for an integration."""
    if not _async_integration_has_notify_services(hass, integration_name):
        return

    tasks = [
        data.service.async_register_services(
            data.service_name, data.target_service_name_prefix, data.targets
        )
        for data in hass.data[NOTIFY_SERVICES][integration_name]
    ]

    await asyncio.gather(*tasks)


@bind_hass
async def async_reset_platform(hass: HomeAssistantType, integration_name: str) -> None:
    """Unregister notify services for an integration."""
    if not _async_integration_has_notify_services(hass, integration_name):
        return

    tasks = [
        data.service.async_unregister_services(data.service_name, data.targets)
        for data in hass.data[NOTIFY_SERVICES][integration_name]
    ]

    await asyncio.gather(*tasks)

    del hass.data[NOTIFY_SERVICES][integration_name]


def _async_integration_has_notify_services(
    hass: HomeAssistantType, integration_name: str
) -> bool:
    """Determine if an integration has notify services registered."""
    if (
        NOTIFY_SERVICES not in hass.data
        or integration_name not in hass.data[NOTIFY_SERVICES]
    ):
        return False

    return True


class BaseNotificationService:
    """An abstract class for notification services."""

    hass: Optional[HomeAssistantType] = None

    def send_message(self, message, **kwargs):
        """Send a message.

        kwargs can contain ATTR_TITLE to specify a title.
        """
        raise NotImplementedError()

    async def async_send_message(self, message: Any, **kwargs: Any) -> None:
        """Send a message.

        kwargs can contain ATTR_TITLE to specify a title.
        """
        await self.hass.async_add_job(partial(self.send_message, message, **kwargs))  # type: ignore

    async def _async_notify_message_service(
        self, service: ServiceCall, targets: Dict
    ) -> None:
        """Handle sending notification message service calls."""
        kwargs = {}
        message = service.data[ATTR_MESSAGE]
        title = service.data.get(ATTR_TITLE)

        if title:
            title.hass = self.hass
            kwargs[ATTR_TITLE] = title.async_render()

        if targets.get(service.service) is not None:
            kwargs[ATTR_TARGET] = [targets[service.service]]
        elif service.data.get(ATTR_TARGET) is not None:
            kwargs[ATTR_TARGET] = service.data.get(ATTR_TARGET)

        message.hass = self.hass
        kwargs[ATTR_MESSAGE] = message.async_render()
        kwargs[ATTR_DATA] = service.data.get(ATTR_DATA)

        await self.async_send_message(**kwargs)

    async def async_register_services(
        self, service_name: str, target_service_name_prefix: str, targets: Dict
    ) -> None:
        """Create or remove the notify services."""
        assert self.hass

        async def _async_notify_message(service):
            """Handle sending notification message service calls."""
            await self._async_notify_message_service(service, targets)

        if hasattr(self, "targets"):
            stale_targets = set(targets)

            # pylint: disable=no-member
            for name, target in self.targets.items():  # type: ignore
                target_name = slugify(f"{target_service_name_prefix}_{name}")
                if target_name in stale_targets:
                    stale_targets.remove(target_name)
                if target_name in targets:
                    continue
                targets[target_name] = target
                self.hass.services.async_register(
                    DOMAIN,
                    target_name,
                    _async_notify_message,
                    schema=NOTIFY_SERVICE_SCHEMA,
                )

            for stale_target_name in stale_targets:
                del targets[stale_target_name]
                self.hass.services.async_remove(
                    DOMAIN,
                    stale_target_name,
                )

        if self.hass.services.has_service(DOMAIN, service_name):
            return

        self.hass.services.async_register(
            DOMAIN,
            service_name,
            _async_notify_message,
            schema=NOTIFY_SERVICE_SCHEMA,
        )

    async def async_unregister_services(self, service_name: str, targets: Dict) -> None:
        """Unregister the notify services."""
        assert self.hass

        if targets:
            remove_targets = set(targets)
            for remove_target_name in remove_targets:
                del targets[remove_target_name]
                self.hass.services.async_remove(
                    DOMAIN,
                    remove_target_name,
                )

        if not self.hass.services.has_service(DOMAIN, service_name):
            return

        self.hass.services.async_remove(
            DOMAIN,
            service_name,
        )


@dataclass
class NotifyServiceData:
    """Class for storing notify service data.

    service
        The NotificationService
    service_name
        The name of the notify service.
    target_service_name_prefix
        The prefix used to create new service for tagets.
    targets
        A dict of targets indexed by service names.
    """

    service: BaseNotificationService
    service_name: str
    target_service_name_prefix: str
    targets: Dict


async def async_setup(hass, config):
    """Set up the notify services."""
    hass.data.setdefault(NOTIFY_SERVICES, {})

    async def async_setup_platform(
        integration_name, p_config=None, discovery_info=None
    ):
        """Set up a notify platform."""
        if p_config is None:
            p_config = {}

        platform = await async_prepare_setup_platform(
            hass, config, DOMAIN, integration_name
        )

        if platform is None:
            _LOGGER.error("Unknown notification service specified")
            return

        _LOGGER.info("Setting up %s.%s", DOMAIN, integration_name)
        notify_service = None
        try:
            if hasattr(platform, "async_get_service"):
                notify_service = await platform.async_get_service(
                    hass, p_config, discovery_info
                )
            elif hasattr(platform, "get_service"):
                notify_service = await hass.async_add_job(
                    platform.get_service, hass, p_config, discovery_info
                )
            else:
                raise HomeAssistantError("Invalid notify platform.")

            if notify_service is None:
                # Platforms can decide not to create a service based
                # on discovery data.
                if discovery_info is None:
                    _LOGGER.error(
                        "Failed to initialize notification service %s", integration_name
                    )
                return

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error setting up platform %s", integration_name)
            return

        notify_service.hass = hass

        if discovery_info is None:
            discovery_info = {}

        conf_name = p_config.get(CONF_NAME) or discovery_info.get(CONF_NAME)
        target_service_name_prefix = conf_name or integration_name
        service_name = slugify(conf_name or SERVICE_NOTIFY)
        targets = {}

        data = NotifyServiceData(
            notify_service, service_name, target_service_name_prefix, targets
        )
        hass.data[NOTIFY_SERVICES].setdefault(integration_name, []).append(data)

        await notify_service.async_register_services(
            service_name, target_service_name_prefix, targets
        )

        hass.config.components.add(f"{DOMAIN}.{integration_name}")

        return True

    setup_tasks = [
        async_setup_platform(integration_name, p_config)
        for integration_name, p_config in config_per_platform(config, DOMAIN)
    ]

    if setup_tasks:
        await asyncio.wait(setup_tasks)

    async def async_platform_discovered(platform, info):
        """Handle for discovered platform."""
        await async_setup_platform(platform, discovery_info=info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)

    return True
