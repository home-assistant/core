"""Provides functionality to notify people."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import timedelta
from enum import StrEnum
from functools import partial
import logging
from typing import Any, final

from typing_extensions import override
import voluptuous as vol

from homeassistant.backports.functools import cached_property
import homeassistant.components.persistent_notification as pn
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_PLATFORM, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

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
    NotifyEntityFeature,
)
from .legacy import (  # noqa: F401
    BaseNotificationService,
    async_reload,
    async_reset_platform,
    async_setup_legacy,
    check_templates_warn,
)

# mypy: disallow-any-generics

# Platform specific data
ATTR_TITLE_DEFAULT = "Home Assistant"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = vol.Schema(
    {vol.Required(CONF_PLATFORM): cv.string, vol.Optional(CONF_NAME): cv.string},
    extra=vol.ALLOW_EXTRA,
)


class NotifyDeviceClass(StrEnum):
    """Device class for notify entities."""

    DIRECT_MESSAGE = "direct_message"
    DISPLAY = "display"
    EMAIL = "email"


DEVICE_CLASSES_SCHEMA = vol.All(vol.Lower, vol.Coerce(NotifyDeviceClass))

SERVICE_SEND_MESSAGE_SCHEMA = cv.make_entity_service_schema(
    {
        vol.Optional(ATTR_MESSAGE): cv.string,
        vol.Optional(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_RECIPIENTS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_DATA): dict,
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the notify services."""

    component = hass.data[DOMAIN] = EntityComponent[NotifyEntity](_LOGGER, DOMAIN, hass)
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_SEND_MESSAGE,
        SERVICE_SEND_MESSAGE_SCHEMA,
        "_async_send_message",
    )

    platform_setups = async_setup_legacy(hass, config)

    # We need to add the component here break the deadlock
    # when setting up integrations from config entries as
    # they would otherwise wait for notify to be
    # setup and thus the config entries would not be able to
    # setup their platforms, but we need to do it after
    # the dispatcher is connected so we don't miss integrations
    # that are registered before the dispatcher is connected
    hass.config.components.add(DOMAIN)

    if platform_setups:
        await asyncio.wait([asyncio.create_task(setup) for setup in platform_setups])

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


class NotifyEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes button entities."""

    device_class: NotifyDeviceClass | None = None


CACHED_PROPERTIES_WITH_ATTR_ = {
    "device_class",
}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[NotifyEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[NotifyEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class NotifyEntity(RestoreEntity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Representation of a nofify entity."""

    entity_description: NotifyEntityDescription
    _attr_should_poll = False
    _attr_device_class: NotifyDeviceClass | None
    _attr_state: None = None
    _attr_supported_features: NotifyEntityFeature = NotifyEntityFeature(0)
    __last_notified_isoformat: str | None = None

    def _default_to_device_class_name(self) -> bool:
        """Return True if an unnamed entity should be named by its device class.

        For buttons this is True if the entity has a device class.
        """
        return self.device_class is not None

    @cached_property
    @override  # type: ignore[override]
    def device_class(self) -> NotifyDeviceClass | None:
        """Return the class of this entity."""
        if hasattr(self, "_attr_device_class"):
            return self._attr_device_class
        if hasattr(self, "entity_description"):
            return self.entity_description.device_class
        return None

    @cached_property
    @final
    @override  # type: ignore[override]
    def state(self) -> str | None:
        """Return the entity state."""
        return self.__last_notified_isoformat

    def __set_state(self, state: str | None) -> None:
        """Set the entity state."""
        try:  # noqa: SIM105  suppress is much slower
            del self.state
        except AttributeError:
            pass
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

    def send_message(
        self,
        message: str | None = None,
        title: str | None = None,
        recipients: list[str] | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> None:
        """Send a message."""
        raise NotImplementedError()

    async def async_send_message(
        self,
        message: str | None = None,
        title: str | None = None,
        recipients: list[str] | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> None:
        """Send a message."""
        await self.hass.async_add_executor_job(
            partial(self.send_message, message, title, recipients, data)
        )
