"""Provides functionality to notify people."""
import asyncio
from functools import partial
import logging
from typing import Any, Dict, Optional

import voluptuous as vol

import homeassistant.components.persistent_notification as pn
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
SERVICE_PERSISTENT_NOTIFICATION = "persistent_notification"

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

PERSISTENT_NOTIFICATION_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MESSAGE): cv.template,
        vol.Optional(ATTR_TITLE): cv.template,
    }
)


@bind_hass
async def async_reload(hass: HomeAssistantType, integration_name: str) -> None:
    """Register notify services for an integration."""
    if not _async_integration_has_notify_services(hass, integration_name):
        return

    tasks = [
        notify_service.async_register_services()
        for notify_service in hass.data[NOTIFY_SERVICES][integration_name]
    ]

    await asyncio.gather(*tasks)


@bind_hass
async def async_reset_platform(hass: HomeAssistantType, integration_name: str) -> None:
    """Unregister notify services for an integration."""
    if not _async_integration_has_notify_services(hass, integration_name):
        return

    tasks = [
        notify_service.async_unregister_services()
        for notify_service in hass.data[NOTIFY_SERVICES][integration_name]
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
    # Name => target
    registered_targets: Dict[str, str]

    def send_message(self, message, **kwargs):
        """Send a message.

        kwargs can contain ATTR_TITLE to specify a title.
        """
        raise NotImplementedError()

    async def async_send_message(self, message: Any, **kwargs: Any) -> None:
        """Send a message.

        kwargs can contain ATTR_TITLE to specify a title.
        """
        await self.hass.async_add_executor_job(partial(self.send_message, message, **kwargs))  # type: ignore

    async def _async_notify_message_service(self, service: ServiceCall) -> None:
        """Handle sending notification message service calls."""
        kwargs = {}
        message = service.data[ATTR_MESSAGE]
        title = service.data.get(ATTR_TITLE)

        if title:
            title.hass = self.hass
            kwargs[ATTR_TITLE] = title.async_render(parse_result=False)

        if self.registered_targets.get(service.service) is not None:
            kwargs[ATTR_TARGET] = [self.registered_targets[service.service]]
        elif service.data.get(ATTR_TARGET) is not None:
            kwargs[ATTR_TARGET] = service.data.get(ATTR_TARGET)

        message.hass = self.hass
        kwargs[ATTR_MESSAGE] = message.async_render(parse_result=False)
        kwargs[ATTR_DATA] = service.data.get(ATTR_DATA)

        await self.async_send_message(**kwargs)

    async def async_setup(
        self,
        hass: HomeAssistantType,
        service_name: str,
        target_service_name_prefix: str,
    ) -> None:
        """Store the data for the notify service."""
        # pylint: disable=attribute-defined-outside-init
        self.hass = hass
        self._service_name = service_name
        self._target_service_name_prefix = target_service_name_prefix
        self.registered_targets = {}

    async def async_register_services(self) -> None:
        """Create or update the notify services."""
        assert self.hass

        if hasattr(self, "targets"):
            stale_targets = set(self.registered_targets)

            # pylint: disable=no-member
            for name, target in self.targets.items():  # type: ignore
                target_name = slugify(f"{self._target_service_name_prefix}_{name}")
                if target_name in stale_targets:
                    stale_targets.remove(target_name)
                if (
                    target_name in self.registered_targets
                    and target == self.registered_targets[target_name]
                ):
                    continue
                self.registered_targets[target_name] = target
                self.hass.services.async_register(
                    DOMAIN,
                    target_name,
                    self._async_notify_message_service,
                    schema=NOTIFY_SERVICE_SCHEMA,
                )

            for stale_target_name in stale_targets:
                del self.registered_targets[stale_target_name]
                self.hass.services.async_remove(
                    DOMAIN,
                    stale_target_name,
                )

        if self.hass.services.has_service(DOMAIN, self._service_name):
            return

        self.hass.services.async_register(
            DOMAIN,
            self._service_name,
            self._async_notify_message_service,
            schema=NOTIFY_SERVICE_SCHEMA,
        )

    async def async_unregister_services(self) -> None:
        """Unregister the notify services."""
        assert self.hass

        if self.registered_targets:
            remove_targets = set(self.registered_targets)
            for remove_target_name in remove_targets:
                del self.registered_targets[remove_target_name]
                self.hass.services.async_remove(
                    DOMAIN,
                    remove_target_name,
                )

        if not self.hass.services.has_service(DOMAIN, self._service_name):
            return

        self.hass.services.async_remove(
            DOMAIN,
            self._service_name,
        )


async def async_setup(hass, config):
    """Set up the notify services."""
    hass.data.setdefault(NOTIFY_SERVICES, {})

    async def persistent_notification(service: ServiceCall) -> None:
        """Send notification via the built-in persistsent_notify integration."""
        payload = {}
        message = service.data[ATTR_MESSAGE]
        message.hass = hass
        payload[ATTR_MESSAGE] = message.async_render(parse_result=False)

        title = service.data.get(ATTR_TITLE)
        if title:
            title.hass = hass
            payload[ATTR_TITLE] = title.async_render(parse_result=False)

        await hass.services.async_call(
            pn.DOMAIN, pn.SERVICE_CREATE, payload, blocking=True
        )

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
                notify_service = await hass.async_add_executor_job(
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

        if discovery_info is None:
            discovery_info = {}

        conf_name = p_config.get(CONF_NAME) or discovery_info.get(CONF_NAME)
        target_service_name_prefix = conf_name or integration_name
        service_name = slugify(conf_name or SERVICE_NOTIFY)

        await notify_service.async_setup(hass, service_name, target_service_name_prefix)
        await notify_service.async_register_services()

        hass.data[NOTIFY_SERVICES].setdefault(integration_name, []).append(
            notify_service
        )
        hass.config.components.add(f"{DOMAIN}.{integration_name}")

        return True

    hass.services.async_register(
        DOMAIN,
        SERVICE_PERSISTENT_NOTIFICATION,
        persistent_notification,
        schema=PERSISTENT_NOTIFICATION_SERVICE_SCHEMA,
    )

    setup_tasks = [
        asyncio.create_task(async_setup_platform(integration_name, p_config))
        for integration_name, p_config in config_per_platform(config, DOMAIN)
    ]

    if setup_tasks:
        await asyncio.wait(setup_tasks)

    async def async_platform_discovered(platform, info):
        """Handle for discovered platform."""
        await async_setup_platform(platform, discovery_info=info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)

    return True
