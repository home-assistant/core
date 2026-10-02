"""Support to interface with universal remote control devices."""

from collections.abc import Iterable
from datetime import timedelta
import functools as ft
import logging
from typing import Any, final, override

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (  # noqa: F401
    ATTR_COMMAND,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .const import (  # noqa: F401
    ATTR_ACTIVITY,
    ATTR_ACTIVITY_LIST,
    ATTR_ALTERNATIVE,
    ATTR_COMMAND_TYPE,
    ATTR_CURRENT_ACTIVITY,
    ATTR_DELAY_SECS,
    ATTR_DEVICE,
    ATTR_HOLD_SECS,
    ATTR_NUM_REPEATS,
    ATTR_TIMEOUT,
    DATA_COMPONENT,
    DEFAULT_DELAY_SECS,
    DEFAULT_HOLD_SECS,
    DEFAULT_NUM_REPEATS,
    DOMAIN,
    SERVICE_DELETE_COMMAND,
    SERVICE_LEARN_COMMAND,
    SERVICE_SEND_COMMAND,
    SERVICE_SYNC,
    RemoteEntityFeature,
    RemoteEntityStateAttribute,
)
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=30)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)


def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return if the remote is on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for remotes."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[RemoteEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class RemoteEntityDescription(ToggleEntityDescription, frozen_or_thawed=True):
    """A class that describes remote entities."""


CACHED_PROPERTIES_WITH_ATTR_ = {
    "supported_features",
    "current_activity",
    "activity_list",
}


class RemoteEntity(ToggleEntity, cached_properties=CACHED_PROPERTIES_WITH_ATTR_):
    """Base class for remote entities."""

    entity_description: RemoteEntityDescription
    _attr_activity_list: list[str] | None = None
    _attr_current_activity: str | None = None
    _attr_supported_features: RemoteEntityFeature = RemoteEntityFeature(0)

    @cached_property
    @override
    def supported_features(self) -> RemoteEntityFeature:
        """Flag supported features."""
        return self._attr_supported_features

    @cached_property
    def current_activity(self) -> str | None:
        """Active activity."""
        return self._attr_current_activity

    @cached_property
    def activity_list(self) -> list[str] | None:
        """List of available activities."""
        return self._attr_activity_list

    @final
    @property
    @override
    def state_attributes(self) -> dict[str, Any] | None:
        """Return optional state attributes."""
        if RemoteEntityFeature.ACTIVITY not in self.supported_features:
            return None

        return {
            RemoteEntityStateAttribute.ACTIVITY_LIST: self.activity_list,
            RemoteEntityStateAttribute.CURRENT_ACTIVITY: self.current_activity,
        }

    def send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send commands to a device."""
        raise NotImplementedError

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send commands to a device."""
        await self.hass.async_add_executor_job(
            ft.partial(self.send_command, command, **kwargs)
        )

    def learn_command(self, **kwargs: Any) -> None:
        """Learn a command from a device."""
        raise NotImplementedError

    async def async_learn_command(self, **kwargs: Any) -> None:
        """Learn a command from a device."""
        await self.hass.async_add_executor_job(ft.partial(self.learn_command, **kwargs))

    def delete_command(self, **kwargs: Any) -> None:
        """Delete commands from the database."""
        raise NotImplementedError

    async def async_delete_command(self, **kwargs: Any) -> None:
        """Delete commands from the database."""
        await self.hass.async_add_executor_job(
            ft.partial(self.delete_command, **kwargs)
        )
