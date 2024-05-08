"""Support to interface with universal remote control devices."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from enum import IntFlag
import functools as ft
from functools import cached_property
import logging
from typing import Any, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_COMMAND,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    make_entity_service_schema,
)
from homeassistant.helpers.deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.entity import ToggleEntity, ToggleEntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

ATTR_ACTIVITY = "activity"
ATTR_ACTIVITY_LIST = "activity_list"
ATTR_CURRENT_ACTIVITY = "current_activity"
ATTR_COMMAND_TYPE = "command_type"
ATTR_DEVICE = "device"
ATTR_NUM_REPEATS = "num_repeats"
ATTR_DELAY_SECS = "delay_secs"
ATTR_HOLD_SECS = "hold_secs"
ATTR_ALTERNATIVE = "alternative"
ATTR_TIMEOUT = "timeout"

DOMAIN = "remote"
SCAN_INTERVAL = timedelta(seconds=30)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)

SERVICE_SEND_COMMAND = "send_command"
SERVICE_LEARN_COMMAND = "learn_command"
SERVICE_DELETE_COMMAND = "delete_command"
SERVICE_SYNC = "sync"

DEFAULT_NUM_REPEATS = 1
DEFAULT_DELAY_SECS = 0.4
DEFAULT_HOLD_SECS = 0


class RemoteEntityFeature(IntFlag):
    """Supported features of the remote entity."""

    LEARN_COMMAND = 1
    DELETE_COMMAND = 2
    ACTIVITY = 4


# These SUPPORT_* constants are deprecated as of Home Assistant 2022.5.
# Please use the RemoteEntityFeature enum instead.
_DEPRECATED_SUPPORT_LEARN_COMMAND = DeprecatedConstantEnum(
    RemoteEntityFeature.LEARN_COMMAND, "2025.1"
)
_DEPRECATED_SUPPORT_DELETE_COMMAND = DeprecatedConstantEnum(
    RemoteEntityFeature.DELETE_COMMAND, "2025.1"
)
_DEPRECATED_SUPPORT_ACTIVITY = DeprecatedConstantEnum(
    RemoteEntityFeature.ACTIVITY, "2025.1"
)


REMOTE_SERVICE_ACTIVITY_SCHEMA = make_entity_service_schema(
    {vol.Optional(ATTR_ACTIVITY): cv.string}
)


@bind_hass
def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return if the remote is on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for remotes."""
    component = hass.data[DOMAIN] = EntityComponent[RemoteEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_TURN_OFF, REMOTE_SERVICE_ACTIVITY_SCHEMA, "async_turn_off"
    )

    component.async_register_entity_service(
        SERVICE_TURN_ON, REMOTE_SERVICE_ACTIVITY_SCHEMA, "async_turn_on"
    )

    component.async_register_entity_service(
        SERVICE_TOGGLE, REMOTE_SERVICE_ACTIVITY_SCHEMA, "async_toggle"
    )

    component.async_register_entity_service(
        SERVICE_SEND_COMMAND,
        {
            vol.Required(ATTR_COMMAND): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_DEVICE): cv.string,
            vol.Optional(
                ATTR_NUM_REPEATS, default=DEFAULT_NUM_REPEATS
            ): cv.positive_int,
            vol.Optional(ATTR_DELAY_SECS): vol.Coerce(float),
            vol.Optional(ATTR_HOLD_SECS, default=DEFAULT_HOLD_SECS): vol.Coerce(float),
        },
        "async_send_command",
    )

    component.async_register_entity_service(
        SERVICE_LEARN_COMMAND,
        {
            vol.Optional(ATTR_DEVICE): cv.string,
            vol.Optional(ATTR_COMMAND): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_COMMAND_TYPE): cv.string,
            vol.Optional(ATTR_ALTERNATIVE): cv.boolean,
            vol.Optional(ATTR_TIMEOUT): cv.positive_int,
        },
        "async_learn_command",
    )

    component.async_register_entity_service(
        SERVICE_DELETE_COMMAND,
        {
            vol.Required(ATTR_COMMAND): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_DEVICE): cv.string,
        },
        "async_delete_command",
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[RemoteEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[RemoteEntity] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


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
    def supported_features(self) -> RemoteEntityFeature:
        """Flag supported features."""
        return self._attr_supported_features

    @property
    def supported_features_compat(self) -> RemoteEntityFeature:
        """Return the supported features as RemoteEntityFeature.

        Remove this compatibility shim in 2025.1 or later.
        """
        features = self.supported_features
        if type(features) is int:  # noqa: E721
            new_features = RemoteEntityFeature(features)
            self._report_deprecated_supported_features_values(new_features)
            return new_features
        return features

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
    def state_attributes(self) -> dict[str, Any] | None:
        """Return optional state attributes."""
        if RemoteEntityFeature.ACTIVITY not in self.supported_features_compat:
            return None

        return {
            ATTR_ACTIVITY_LIST: self.activity_list,
            ATTR_CURRENT_ACTIVITY: self.current_activity,
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


# These can be removed if no deprecated constant are in this module anymore
__getattr__ = ft.partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = ft.partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
