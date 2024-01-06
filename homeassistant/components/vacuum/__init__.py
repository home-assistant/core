"""Support for vacuum cleaner robots (botvacs)."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import timedelta
from enum import IntFlag
from functools import partial
import logging
from typing import TYPE_CHECKING, Any, final

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (  # noqa: F401 # STATE_PAUSED/IDLE are API
    ATTR_BATTERY_LEVEL,
    ATTR_COMMAND,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_IDLE,
    STATE_ON,
    STATE_PAUSED,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
    make_entity_service_schema,
)
from homeassistant.helpers.entity import (
    Entity,
    EntityDescription,
    ToggleEntity,
    ToggleEntityDescription,
)
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import (
    async_get_issue_tracker,
    async_suggest_report_issue,
    bind_hass,
)

if TYPE_CHECKING:
    from functools import cached_property
else:
    from homeassistant.backports.functools import cached_property

_LOGGER = logging.getLogger(__name__)

DOMAIN = "vacuum"
ENTITY_ID_FORMAT = DOMAIN + ".{}"
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


STATE_CLEANING = "cleaning"
STATE_DOCKED = "docked"
STATE_RETURNING = "returning"
STATE_ERROR = "error"

STATES = [STATE_CLEANING, STATE_DOCKED, STATE_RETURNING, STATE_ERROR]

DEFAULT_NAME = "Vacuum cleaner robot"


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
SUPPORT_TURN_ON = 1
SUPPORT_TURN_OFF = 2
SUPPORT_PAUSE = 4
SUPPORT_STOP = 8
SUPPORT_RETURN_HOME = 16
SUPPORT_FAN_SPEED = 32
SUPPORT_BATTERY = 64
SUPPORT_STATUS = 128
SUPPORT_SEND_COMMAND = 256
SUPPORT_LOCATE = 512
SUPPORT_CLEAN_SPOT = 1024
SUPPORT_MAP = 2048
SUPPORT_STATE = 4096
SUPPORT_START = 8192

# mypy: disallow-any-generics


@bind_hass
def is_on(hass: HomeAssistant, entity_id: str) -> bool:
    """Return if the vacuum is on based on the statemachine."""
    return hass.states.is_state(entity_id, STATE_ON)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the vacuum component."""
    component = hass.data[DOMAIN] = EntityComponent[_BaseVacuum](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )

    await component.async_setup(config)

    component.async_register_entity_service(
        SERVICE_TURN_ON,
        {},
        "async_turn_on",
        [VacuumEntityFeature.TURN_ON],
    )
    component.async_register_entity_service(
        SERVICE_TURN_OFF,
        {},
        "async_turn_off",
        [VacuumEntityFeature.TURN_OFF],
    )
    component.async_register_entity_service(
        SERVICE_TOGGLE,
        {},
        "async_toggle",
        [VacuumEntityFeature.TURN_OFF | VacuumEntityFeature.TURN_ON],
    )
    # start_pause is a legacy service, only supported by VacuumEntity, and only needs
    # VacuumEntityFeature.PAUSE
    component.async_register_entity_service(
        SERVICE_START_PAUSE,
        {},
        "async_start_pause",
        [VacuumEntityFeature.PAUSE],
    )
    component.async_register_entity_service(
        SERVICE_START,
        {},
        "async_start",
        [VacuumEntityFeature.START],
    )
    component.async_register_entity_service(
        SERVICE_PAUSE,
        {},
        "async_pause",
        [VacuumEntityFeature.PAUSE],
    )
    component.async_register_entity_service(
        SERVICE_RETURN_TO_BASE,
        {},
        "async_return_to_base",
        [VacuumEntityFeature.RETURN_HOME],
    )
    component.async_register_entity_service(
        SERVICE_CLEAN_SPOT,
        {},
        "async_clean_spot",
        [VacuumEntityFeature.CLEAN_SPOT],
    )
    component.async_register_entity_service(
        SERVICE_LOCATE,
        {},
        "async_locate",
        [VacuumEntityFeature.LOCATE],
    )
    component.async_register_entity_service(
        SERVICE_STOP,
        {},
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
    component: EntityComponent[_BaseVacuum] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[_BaseVacuum] = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


BASE_CACHED_PROPERTIES_WITH_ATTR_ = {
    "supported_features",
    "battery_level",
    "battery_icon",
    "fan_speed",
    "fan_speed_list",
}


class _BaseVacuum(Entity, cached_properties=BASE_CACHED_PROPERTIES_WITH_ATTR_):
    """Representation of a base vacuum.

    Contains common properties and functions for all vacuum devices.
    """

    _entity_component_unrecorded_attributes = frozenset({ATTR_FAN_SPEED_LIST})

    _attr_battery_icon: str
    _attr_battery_level: int | None = None
    _attr_fan_speed: str | None = None
    _attr_fan_speed_list: list[str]
    _attr_supported_features: VacuumEntityFeature = VacuumEntityFeature(0)

    @cached_property
    def supported_features(self) -> VacuumEntityFeature:
        """Flag vacuum cleaner features that are supported."""
        return self._attr_supported_features

    @property
    def supported_features_compat(self) -> VacuumEntityFeature:
        """Return the supported features as VacuumEntityFeature.

        Remove this compatibility shim in 2025.1 or later.
        """
        features = self.supported_features
        if type(features) is int:  # noqa: E721
            new_features = VacuumEntityFeature(features)
            self._report_deprecated_supported_features_values(new_features)
            return new_features
        return features

    @cached_property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum cleaner."""
        return self._attr_battery_level

    @cached_property
    def battery_icon(self) -> str:
        """Return the battery icon for the vacuum cleaner."""
        return self._attr_battery_icon

    @cached_property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self._attr_fan_speed

    @cached_property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return self._attr_fan_speed_list

    @property
    def capability_attributes(self) -> Mapping[str, Any] | None:
        """Return capability attributes."""
        if VacuumEntityFeature.FAN_SPEED in self.supported_features_compat:
            return {ATTR_FAN_SPEED_LIST: self.fan_speed_list}
        return None

    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the vacuum cleaner."""
        data: dict[str, Any] = {}
        supported_features = self.supported_features_compat

        if VacuumEntityFeature.BATTERY in supported_features:
            data[ATTR_BATTERY_LEVEL] = self.battery_level
            data[ATTR_BATTERY_ICON] = self.battery_icon

        if VacuumEntityFeature.FAN_SPEED in supported_features:
            data[ATTR_FAN_SPEED] = self.fan_speed

        return data

    def stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        raise NotImplementedError()

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.stop, **kwargs))

    def return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        raise NotImplementedError()

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.return_to_base, **kwargs))

    def clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean-up."""
        raise NotImplementedError()

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean-up.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.clean_spot, **kwargs))

    def locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner."""
        raise NotImplementedError()

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.locate, **kwargs))

    def set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        raise NotImplementedError()

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
        raise NotImplementedError()

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


class VacuumEntityDescription(ToggleEntityDescription, frozen_or_thawed=True):
    """A class that describes vacuum entities."""


VACUUM_CACHED_PROPERTIES_WITH_ATTR_ = {
    "status",
}


class VacuumEntity(
    _BaseVacuum, ToggleEntity, cached_properties=VACUUM_CACHED_PROPERTIES_WITH_ATTR_
):
    """Representation of a vacuum cleaner robot."""

    @callback
    def add_to_platform_start(
        self,
        hass: HomeAssistant,
        platform: EntityPlatform,
        parallel_updates: asyncio.Semaphore | None,
    ) -> None:
        """Start adding an entity to a platform."""
        super().add_to_platform_start(hass, platform, parallel_updates)
        # Don't report core integrations known to still use the deprecated base class;
        # we don't worry about demo and mqtt has it's own deprecation warnings.
        if self.platform.platform_name in ("demo", "mqtt"):
            return
        translation_key = "deprecated_vacuum_base_class"
        translation_placeholders = {"platform": self.platform.platform_name}
        issue_tracker = async_get_issue_tracker(
            hass,
            integration_domain=self.platform.platform_name,
            module=type(self).__module__,
        )
        if issue_tracker:
            translation_placeholders["issue_tracker"] = issue_tracker
            translation_key = "deprecated_vacuum_base_class_url"
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_vacuum_base_class_{self.platform.platform_name}",
            breaks_in_ha_version="2024.2.0",
            is_fixable=False,
            is_persistent=False,
            issue_domain=self.platform.platform_name,
            severity=ir.IssueSeverity.WARNING,
            translation_key=translation_key,
            translation_placeholders=translation_placeholders,
        )

        report_issue = async_suggest_report_issue(
            hass,
            integration_domain=self.platform.platform_name,
            module=type(self).__module__,
        )
        _LOGGER.warning(
            (
                "%s::%s is extending the deprecated base class VacuumEntity instead of "
                "StateVacuumEntity, this is not valid and will be unsupported "
                "from Home Assistant 2024.2. Please %s"
            ),
            self.platform.platform_name,
            self.__class__.__name__,
            report_issue,
        )

    entity_description: VacuumEntityDescription
    _attr_status: str | None = None

    @cached_property
    def status(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        return self._attr_status

    @property
    def battery_icon(self) -> str:
        """Return the battery icon for the vacuum cleaner."""
        charging = False
        if self.status is not None:
            charging = "charg" in self.status.lower()
        return icon_for_battery_level(
            battery_level=self.battery_level, charging=charging
        )

    @final
    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the vacuum cleaner."""
        data = super().state_attributes

        if VacuumEntityFeature.STATUS in self.supported_features_compat:
            data[ATTR_STATUS] = self.status

        return data

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the vacuum on and start cleaning."""
        raise NotImplementedError()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the vacuum on and start cleaning.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.turn_on, **kwargs))

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the vacuum off stopping the cleaning and returning home."""
        raise NotImplementedError()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the vacuum off stopping the cleaning and returning home.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.turn_off, **kwargs))

    def start_pause(self, **kwargs: Any) -> None:
        """Start, pause or resume the cleaning task."""
        raise NotImplementedError()

    async def async_start_pause(self, **kwargs: Any) -> None:
        """Start, pause or resume the cleaning task.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(partial(self.start_pause, **kwargs))


class StateVacuumEntityDescription(EntityDescription, frozen_or_thawed=True):
    """A class that describes vacuum entities."""


STATE_VACUUM_CACHED_PROPERTIES_WITH_ATTR_ = {
    "state",
}


class StateVacuumEntity(
    _BaseVacuum, cached_properties=STATE_VACUUM_CACHED_PROPERTIES_WITH_ATTR_
):
    """Representation of a vacuum cleaner robot that supports states."""

    entity_description: StateVacuumEntityDescription
    _attr_state: str | None = None

    @cached_property
    def state(self) -> str | None:
        """Return the state of the vacuum cleaner."""
        return self._attr_state

    @property
    def battery_icon(self) -> str:
        """Return the battery icon for the vacuum cleaner."""
        charging = bool(self.state == STATE_DOCKED)

        return icon_for_battery_level(
            battery_level=self.battery_level, charging=charging
        )

    def start(self) -> None:
        """Start or resume the cleaning task."""
        raise NotImplementedError()

    async def async_start(self) -> None:
        """Start or resume the cleaning task.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(self.start)

    def pause(self) -> None:
        """Pause the cleaning task."""
        raise NotImplementedError()

    async def async_pause(self) -> None:
        """Pause the cleaning task.

        This method must be run in the event loop.
        """
        await self.hass.async_add_executor_job(self.pause)
