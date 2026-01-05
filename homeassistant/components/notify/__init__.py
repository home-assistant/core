"""Provides functionality to notify people."""

from __future__ import annotations

from datetime import timedelta
from enum import IntFlag
from functools import partial
import logging
from typing import Any, final, override

from propcache.api import cached_property
import voluptuous as vol

from homeassistant.components import persistent_notification as pn
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PLATFORM, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import (  # noqa: F401
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_RECIPIENTS,
    ATTR_TARGET,
    ATTR_TITLE,
    DOMAIN,
    NOTIFY_SERVICE_SCHEMA,
    SERVICE_NOTIFY,
    SERVICE_PERSISTENT_NOTIFICATION,
    SERVICE_SEND_MESSAGE,
)
from .legacy import (  # noqa: F401
    BaseNotificationService,
    async_reload,
    async_reset_platform,
    async_setup_legacy,
)
from .repairs import migrate_notify_issue  # noqa: F401

# mypy: disallow-any-generics

# Platform specific data
ATTR_TITLE_DEFAULT = "Home Assistant"

DATA_COMPONENT: HassKey[EntityComponent[NotifyEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.Schema(
    {vol.Required(CONF_PLATFORM): cv.string, vol.Optional(CONF_NAME): cv.string},
    extra=vol.ALLOW_EXTRA,
)


class NotifyEntityFeature(IntFlag):
    """Supported features of a notify entity."""

    TITLE = 1


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

    component = hass.data[DATA_COMPONENT] = EntityComponent[NotifyEntity](
        _LOGGER, DOMAIN, hass
    )
    component.async_register_entity_service(
        SERVICE_SEND_MESSAGE,
        {
            vol.Required(ATTR_MESSAGE): cv.string,
            vol.Optional(ATTR_TITLE): cv.string,
        },
        "_async_send_message",
    )

    async def persistent_notification(service: ServiceCall) -> None:
        """Send notification via the built-in persistent_notify integration."""
        message: str = service.data[ATTR_MESSAGE]
        title: str | None = service.data.get(ATTR_TITLE)

        notification_id = None
        if data := service.data.get(ATTR_DATA):
            notification_id = data.get(pn.ATTR_NOTIFICATION_ID)

        pn.async_create(hass, message, title, notification_id)

    hass.services.async_register(
        DOMAIN,
        SERVICE_PERSISTENT_NOTIFICATION,
        persistent_notification,
        schema=NOTIFY_SERVICE_SCHEMA,
    )

    return True


class NotifyEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes button entities."""


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class NotifyEntity(RestoreEntity):
    """Representation of a notify entity."""

    entity_description: NotifyEntityDescription
    _attr_supported_features: NotifyEntityFeature = NotifyEntityFeature(0)
    _attr_should_poll = False
    _attr_device_class: None
    _attr_state: None = None
    __last_notified_isoformat: str | None = None

    @cached_property
    @final
    @override
    def state(self) -> str | None:
        """Return the entity state."""
        return self.__last_notified_isoformat

    def __set_state(self, state: str | None) -> None:
        """Invalidate the cache of the cached property."""
        self.__dict__.pop("state", None)
        self.__last_notified_isoformat = state

    async def async_internal_added_to_hass(self) -> None:
        """Call when the notify entity is added to hass."""
        await super().async_internal_added_to_hass()
        state = await self.async_get_last_state()
        if state is not None and state.state not in (STATE_UNAVAILABLE, None):
            self.__set_state(state.state)

    @final
    async def _async_send_message(self, **kwargs: Any) -> None:
        """Send a notification message (from e.g., service call).

        Should not be overridden, handle setting last notification timestamp.
        """
        self.__set_state(dt_util.utcnow().isoformat())
        self.async_write_ha_state()
        await self.async_send_message(**kwargs)

    def send_message(self, message: str, title: str | None = None) -> None:
        """Send a message."""
        raise NotImplementedError

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Send a message."""
        kwargs: dict[str, Any] = {}
        if (
            title is not None
            and self.supported_features
            and self.supported_features & NotifyEntityFeature.TITLE
        ):
            kwargs[ATTR_TITLE] = title
        await self.hass.async_add_executor_job(
            partial(self.send_message, message, **kwargs)
        )
