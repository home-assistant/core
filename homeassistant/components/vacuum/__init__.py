"""Support for vacuum cleaner robots (botvacs)."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from enum import IntFlag
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, final

from propcache import cached_property
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (  # noqa: F401 # STATE_PAUSED/IDLE are API
    ATTR_BATTERY_LEVEL,
    ATTR_COMMAND,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.frame import ReportBehavior, report_usage
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass
from homeassistant.util.hass_dict import HassKey

from .const import (  # noqa: F401
    _DEPRECATED_STATE_CLEANING,
    _DEPRECATED_STATE_DOCKED,
    _DEPRECATED_STATE_ERROR,
    _DEPRECATED_STATE_RETURNING,
    DOMAIN,
    VacuumActivity,
)

_LOGGER = logging.getLogger(__name__)

DATA_COMPONENT: HassKey[EntityComponent[StateVacuumEntity]] = HassKey(DOMAIN)
ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=20)

ATTR_BATTERY_ICON = "battery_icon"
ATTR_CLEANED_AREA = "cleaned_area"
ATTR_FAN_SPEED = "fan_speed"
ATTR_FAN_SPEED_LIST = "fan_speed_list"
ATTR_PARAMS = "params"
ATTR_STATUS = "status"

SERVICE_CLEAN_SPOT = "clean_spot"
SERVICE_LOCATE = "locate"
SERVICE_RETURN_TO_BASE = "return_to_base"
SERVICE_SEND_COMMAND = "send_command"
SERVICE_SET_FAN_SPEED = "set_fan_speed"
SERVICE_START_PAUSE = "start_pause"
SERVICE_START = "start"
SERVICE_PAUSE = "pause"
SERVICE_STOP = "stop"

DEFAULT_NAME = "Vacuum cleaner robot"

# These STATE_* constants are deprecated as of Home Assistant 2025.1.
# Please use the VacuumActivity enum instead.
_DEPRECATED_STATE_IDLE = DeprecatedConstantEnum(VacuumActivity.IDLE, "2026.1")
_DEPRECATED_STATE_PAUSED = DeprecatedConstantEnum(VacuumActivity.PAUSED, "2026.1")


class VacuumEntityFeature(IntFlag):
    """Supported features of the vacuum entity."""

    TURN_ON = 1  # Deprecated, not supported by StateVacuumEntity
    TURN_OFF = 2  # Deprecated, not supported by StateVacuumEntity
    PAUSE = 4
    STOP = 8
    RETURN_HOME = 16
    FAN_SPEED = 32
    BATTERY = 64
    STATUS = 128  # Deprecated, not supported by StateVacuumEntity
    SEND_COMMAND = 256
    LOCATE = 512
    CLEAN_SPOT = 1024
    MAP = 2048
    STATE = 4096  # Must be set by vacuum platforms derived from StateVacuumEntity
    START = 8192


# These SUPPORT_* constants are deprecated as of Home Assistant 2022.5.
# Please use the VacuumEntityFeature enum instead.
_DEPRECATED_SUPPORT_TURN_ON = DeprecatedConstantEnum(
    VacuumEntityFeature.TURN_ON, "2025.10"
)
_DEPRECATED_SUPPORT_TURN_OFF = DeprecatedConstantEnum(
    VacuumEntityFeature.TURN_OFF, "2025.10"
)
_DEPRECATED_SUPPORT_PAUSE = DeprecatedConstantEnum(VacuumEntityFeature.PAUSE, "2025.10")
_DEPRECATED_SUPPORT_STOP = DeprecatedConstantEnum(VacuumEntityFeature.STOP, "2025.10")
_DEPRECATED_SUPPORT_RETURN_HOME = DeprecatedConstantEnum(
    VacuumEntityFeature.RETURN_HOME, "2025.10"
)
_DEPRECATED_SUPPORT_FAN_SPEED = DeprecatedConstantEnum(
    VacuumEntityFeature.FAN_SPEED, "2025.10"
)
_DEPRECATED_SUPPORT_BATTERY = DeprecatedConstantEnum(
    VacuumEntityFeature.BATTERY, "2025.10"
)
_DEPRECATED_SUPPORT_STATUS = DeprecatedConstantEnum(
    VacuumEntityFeature.STATUS, "2025.10"
)
_DEPRECATED_SUPPORT_SEND_COMMAND = DeprecatedConstantEnum(
    VacuumEntityFeature.SEND_COMMAND, "2025.10"
)
_DEPRECATED_SUPPORT_LOCATE = DeprecatedConstantEnum(
    VacuumEntityFeature.LOCATE, "2025.10"
)
_DEPRECATED_SUPPORT_CLEAN_SPOT = DeprecatedConstantEnum(
    VacuumEntityFeature.CLEAN_SPOT, "2025.10"
)
_DEPRECATED_SUPPORT_MAP = DeprecatedConstantEnum(VacuumEntityFeature.MAP, "2025.10")
_DEPRECATED_SUPPORT_STATE = DeprecatedConstantEnum(VacuumEntityFeature.STATE, "2025.10")
_DEPRECATED_SUPPORT_START = DeprecatedConstantEnum(VacuumEntityFeature.START, "2025.10")

# mypy: disallow-any-generics


@bind_hass
def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return if the vacuum is on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the vacuum component."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[StateVacuumEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_START,
        None,
        "async_start",
        [VacuumEntityFeature.START],
    )
    component.async_register_entity_service(
        SERVICE_PAUSE,
        None,
        "async_pause",
        [VacuumEntityFeature.PAUSE],
    )
    component.async_register_entity_service(
        SERVICE_RETURN_TO_BASE,
        None,
        "async_return_to_base",
        [VacuumEntityFeature.RETURN_HOME],
    )
    component.async_register_entity_service(
        SERVICE_CLEAN_SPOT,
        None,
        "async_clean_spot",
        [VacuumEntityFeature.CLEAN_SPOT],
    )
    component.async_register_entity_service(
        SERVICE_LOCATE,
        None,
        "async_locate",
        [VacuumEntityFeature.LOCATE],
    )
    component.async_register_entity_service(
        SERVICE_STOP,
        None,
        "async_stop",
        [VacuumEntityFeature.STOP],
    )
    component.async_register_entity_service(
        SERVICE_SET_FAN_SPEED,
        {vol.Required(ATTR_FAN_SPEED): cv.string},
        "async_set_fan_speed",
        [VacuumEntityFeature.FAN_SPEED],
    )
    component.async_register_entity_service(
        SERVICE_SEND_COMMAND,
        {
            vol.Required(ATTR_COMMAND): cv.string,
            vol.Optional(ATTR_PARAMS): vol.Any(dict, cv.ensure_list),
        },
        "async_send_command",
        [VacuumEntityFeature.SEND_COMMAND],
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    return await hass.data[DATA_COMPONENT].async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class StateVacuumEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes vacuum entities."""


STATE_VACUUM_CACHED_PROPERTIES_WITH_ATTR_ = {
    "supported_features",
    "battery_level",
    "battery_icon",
    "fan_speed",
    "fan_speed_list",
    "activity",
}


class StateVacuumEntity(
    Entity, cached_properties=STATE_VACUUM_CACHED_PROPERTIES_WITH_ATTR_
):
    """Representation of a vacuum cleaner robot that supports states."""

    entity_description: StateVacuumEntityDescription

    _entity_component_unrecorded_attributes = frozenset({ATTR_FAN_SPEED_LIST})

    _attr_battery_icon: str
    _attr_battery_level: int | None = None
    _attr_fan_speed: str | None = None
    _attr_fan_speed_list: list[str]
    _attr_activity: VacuumActivity | None = None
    _attr_supported_features: VacuumEntityFeature = VacuumEntityFeature(0)

    __vacuum_legacy_state: bool = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Post initialisation processing."""
        super().__init_subclass__(**kwargs)
        if any(method in cls.__dict__ for method in ("_attr_state", "state")):
            # Integrations should use the 'activity' property instead of
            # setting the state directly.
            cls.__vacuum_legacy_state = True

    def __setattr__(self, name: str, value: Any) -> None:
        """Set attribute.

        Deprecation warning if setting '_attr_state' directly
        unless already reported.
        """
        if name == "_attr_state":
            self._report_deprecated_activity_handling()
        return super().__setattr__(name, value)

    @callback
    def add_to_platform_start(
        self,
        hass: HomeAssistant,
        platform: EntityPlatform,
        parallel_updates: asyncio.Semaphore | None,
    ) -> None:
        """Start adding an entity to a platform."""
        super().add_to_platform_start(hass, platform, parallel_updates)
        if self.__vacuum_legacy_state:
            self._report_deprecated_activity_handling()

    @callback
    def _report_deprecated_activity_handling(self) -> None:
        """Report on deprecated handling of vacuum state.

        Integrations should implement activity instead of using state directly.
        """
        report_usage(
            "is setting state directly."
            f" Entity {self.entity_id} ({type(self)}) should implement the 'activity'"
            " property and return its state using the VacuumActivity enum",
            core_integration_behavior=ReportBehavior.ERROR,
            custom_integration_behavior=ReportBehavior.LOG,
            breaks_in_ha_version="2026.1",
            integration_domain=self.platform.platform_name if self.platform else None,
            exclude_integrations={DOMAIN},
        )

    @cached_property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum cleaner."""
        return self._attr_battery_level

    @property
    def battery_icon(self) -> str:
        """Return the battery icon for the vacuum cleaner."""
        charging = bool(self.activity == VacuumActivity.DOCKED)

        return icon_for_battery_level(
            battery_level=self.battery_level, charging=charging
        )

    @property
    def capability_attributes(self) -> dict[str, Any] | None:
        """Return capability attributes."""
        if VacuumEntityFeature.FAN_SPEED in self.supported_features:
            return {ATTR_FAN_SPEED_LIST: self.fan_speed_list}
        return None

    @cached_property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self._attr_fan_speed

    @cached_property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return self._attr_fan_speed_list

    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the vacuum cleaner."""
        data: dict[str, Any] = {}
        supported_features = self.supported_features

        if VacuumEntityFeature.BATTERY in supported_features:
            data[ATTR_BATTERY_LEVEL] = self.battery_level
            data[ATTR_BATTERY_ICON] = self.battery_icon

        if VacuumEntityFeature.FAN_SPEED in supported_features:
            data[ATTR_FAN_SPEED] = self.fan_speed

        return data

    @final
    @property
    def state(self) -> str | None:
        """Return the state of the vacuum cleaner."""
        if (activity := self.activity) is not None:
            return activity
        if self._attr_state is not None:
            # Backwards compatibility for integrations that set state directly
            # Should be removed in 2026.1
            if TYPE_CHECKING:
                assert isinstance(self._attr_state, str)
            return self._attr_state
        return None

    @cached_property
    def activity(self) -> VacuumActivity | None:
        """Return the current vacuum activity.

        Integrations should overwrite this or use the '_attr_activity'
        attribute to set the vacuum activity using the 'VacuumActivity' enum.
        """
        return self._attr_activity

    @cached_property
    def supported_features(self) -> VacuumEntityFeature:
        """Flag vacuum cleaner features that are supported."""
        return self._attr_supported_features

    def stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        raise NotImplementedError

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.stop, **kwargs))

    def return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        raise NotImplementedError

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.return_to_base, **kwargs))

    def clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean-up."""
        raise NotImplementedError

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean-up.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.clean_spot, **kwargs))

    def locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner."""
        raise NotImplementedError

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.locate, **kwargs))

    def set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        raise NotImplementedError

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(
            partial(self.set_fan_speed, fan_speed, **kwargs)
        )

    def send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner."""
        raise NotImplementedError

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(
            partial(self.send_command, command, params=params, **kwargs)
        )

    def start(self) -> None:
        """Start or resume the cleaning task."""
        raise NotImplementedError

    async def async_start(self) -> None:
        """Start or resume the cleaning task.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(self.start)

    def pause(self) -> None:
        """Pause the cleaning task."""
        raise NotImplementedError

    async def async_pause(self) -> None:
        """Pause the cleaning task.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(self.pause)


# As we import deprecated constants from the const module, we need to add these two functions
# otherwise this module will be logged for using deprecated constants and not the custom component
# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
