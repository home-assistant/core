"""
Provides functionality to notify people.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/notify/
"""
import asyncio
import logging
from functools import partial

import voluptuous as vol

from homeassistant.setup import async_prepare_setup_platform
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import bind_hass
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.helpers import config_per_platform, discovery
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

# Platform specific data
ATTR_DATA = 'data'

# Text to notify user of
ATTR_MESSAGE = 'message'

# Target of the notification (user, device, etc)
ATTR_TARGET = 'target'

# Title of notification
ATTR_TITLE = 'title'
ATTR_TITLE_DEFAULT = "Home Assistant"

DOMAIN = 'notify'

SERVICE_NOTIFY = 'notify'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): cv.string,
    vol.Optional(CONF_NAME): cv.string,
}, extra=vol.ALLOW_EXTRA)

NOTIFY_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.template,
    vol.Optional(ATTR_TITLE): cv.template,
    vol.Optional(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(ATTR_DATA): dict,
})


@bind_hass
def send_message(hass, message, title=None, data=None):
    """Send a notification message."""
    info = {
        ATTR_MESSAGE: message
    }

    if title is not None:
        info[ATTR_TITLE] = title

    if data is not None:
        info[ATTR_DATA] = data

    hass.services.call(DOMAIN, SERVICE_NOTIFY, info)


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the notify services."""
    targets = {}

    @asyncio.coroutine
    def async_setup_platform(p_type, p_config=None, discovery_info=None):
        """Set up a notify platform."""
        if p_config is None:
            p_config = {}

        platform = yield from async_prepare_setup_platform(
            hass, config, DOMAIN, p_type)

        if platform is None:
            _LOGGER.error("Unknown notification service specified")
            return

        _LOGGER.info("Setting up %s.%s", DOMAIN, p_type)
        notify_service = None
        try:
            if hasattr(platform, 'async_get_service'):
                notify_service = yield from \
                    platform.async_get_service(hass, p_config, discovery_info)
            elif hasattr(platform, 'get_service'):
                notify_service = yield from hass.async_add_job(
                    platform.get_service, hass, p_config, discovery_info)
            else:
                raise HomeAssistantError("Invalid notify platform.")

            if notify_service is None:
                # Platforms can decide not to create a service based
                # on discovery data.
                if discovery_info is None:
                    _LOGGER.error(
                        "Failed to initialize notification service %s",
                        p_type)
                return

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception('Error setting up platform %s', p_type)
            return

        notify_service.hass = hass

        if discovery_info is None:
            discovery_info = {}

        @asyncio.coroutine
        def async_notify_message(service):
            """Handle sending notification message service calls."""
            kwargs = {}
            message = service.data[ATTR_MESSAGE]
            title = service.data.get(ATTR_TITLE)

            if title:
                title.hass = hass
                kwargs[ATTR_TITLE] = title.async_render()

            if targets.get(service.service) is not None:
                kwargs[ATTR_TARGET] = [targets[service.service]]
            elif service.data.get(ATTR_TARGET) is not None:
                kwargs[ATTR_TARGET] = service.data.get(ATTR_TARGET)

            message.hass = hass
            kwargs[ATTR_MESSAGE] = message.async_render()
            kwargs[ATTR_DATA] = service.data.get(ATTR_DATA)

            yield from notify_service.async_send_message(**kwargs)

        if hasattr(notify_service, 'targets'):
            platform_name = (
                p_config.get(CONF_NAME) or discovery_info.get(CONF_NAME) or
                p_type)
            for name, target in notify_service.targets.items():
                target_name = slugify('{}_{}'.format(platform_name, name))
                targets[target_name] = target
                hass.services.async_register(
                    DOMAIN, target_name, async_notify_message,
                    schema=NOTIFY_SERVICE_SCHEMA)

        platform_name = (
            p_config.get(CONF_NAME) or discovery_info.get(CONF_NAME) or
            SERVICE_NOTIFY)
        platform_name_slug = slugify(platform_name)

        hass.services.async_register(
            DOMAIN, platform_name_slug, async_notify_message,
            schema=NOTIFY_SERVICE_SCHEMA)

        hass.config.components.add('{}.{}'.format(DOMAIN, p_type))

        return True

    setup_tasks = [async_setup_platform(p_type, p_config) for p_type, p_config
                   in config_per_platform(config, DOMAIN)]

    if setup_tasks:
        yield from asyncio.wait(setup_tasks, loop=hass.loop)

    @asyncio.coroutine
    def async_platform_discovered(platform, info):
        """Handle for discovered platform."""
        yield from async_setup_platform(platform, discovery_info=info)

    discovery.async_listen_platform(hass, DOMAIN, async_platform_discovered)

    return True


class BaseNotificationService:
    """An abstract class for notification services."""

    hass = None

    def send_message(self, message, **kwargs):
        """Send a message.

        kwargs can contain ATTR_TITLE to specify a title.
        """
        raise NotImplementedError()

    def async_send_message(self, message, **kwargs):
        """Send a message.

        kwargs can contain ATTR_TITLE to specify a title.
        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(
            partial(self.send_message, message, **kwargs))
