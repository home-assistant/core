"""Support for vacuum cleaner robots (botvacs)."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
import logging
from typing import Any, final

from propcache.api import cached_property
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
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import EntityPlatform
from homeassistant.helpers.frame import ReportBehavior, report_usage
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import bind_hass

from .const import DATA_COMPONENT, DOMAIN, VacuumActivity, VacuumEntityFeature
from .websocket import async_register_websocket_handlers

_LOGGER = logging.getLogger(__name__)

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
SERVICE_CLEAN_AREA = "clean_area"
SERVICE_LOCATE = "locate"
SERVICE_RETURN_TO_BASE = "return_to_base"
SERVICE_SEND_COMMAND = "send_command"
SERVICE_SET_FAN_SPEED = "set_fan_speed"
SERVICE_START_PAUSE = "start_pause"
SERVICE_START = "start"
SERVICE_PAUSE = "pause"
SERVICE_STOP = "stop"

DEFAULT_NAME = "Vacuum cleaner robot"

ISSUE_SEGMENTS_CHANGED = "segments_changed"

_BATTERY_DEPRECATION_IGNORED_PLATFORMS = ("template",)


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

    async_register_websocket_handlers(hass)

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
        SERVICE_CLEAN_AREA,
        {
            vol.Required("cleaning_area_id"): vol.All(cv.ensure_list, [str]),
        },
        "async_internal_clean_area",
        [VacuumEntityFeature.CLEAN_AREA],
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

    __vacuum_legacy_battery_level: bool = False
    __vacuum_legacy_battery_icon: bool = False
    __vacuum_legacy_battery_feature: bool = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Post initialisation processing."""
        super().__init_subclass__(**kwargs)
        if any(
            method in cls.__dict__
            for method in ("_attr_battery_level", "battery_level")
        ):
            # Integrations should use a separate battery sensor.
            cls.__vacuum_legacy_battery_level = True
        if any(
            method in cls.__dict__ for method in ("_attr_battery_icon", "battery_icon")
        ):
            # Integrations should use a separate battery sensor.
            cls.__vacuum_legacy_battery_icon = True

    def __setattr__(self, name: str, value: Any) -> None:
        """Set attribute.

        Deprecation warning if setting battery icon or battery level
        attributes directly unless already reported.
        """
        if name in {"_attr_battery_level", "_attr_battery_icon"}:
            self._report_deprecated_battery_properties(name[6:])
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
        if self.__vacuum_legacy_battery_level:
            self._report_deprecated_battery_properties("battery_level")
        if self.__vacuum_legacy_battery_icon:
            self._report_deprecated_battery_properties("battery_icon")

    @callback
    def _report_deprecated_battery_properties(self, property: str) -> None:
        """Report on deprecated use of battery properties.

        Integrations should implement a sensor instead.
        """
        if (
            self.platform
            and self.platform.platform_name
            not in _BATTERY_DEPRECATION_IGNORED_PLATFORMS
        ):
            # Don't report usage until after entity added to hass, after init
            report_usage(
                f"is setting the {property} which has been deprecated."
                f" Integration {self.platform.platform_name} should implement a sensor"
                " instead with a correct device class and link it to the same device",
                core_integration_behavior=ReportBehavior.IGNORE,
                custom_integration_behavior=ReportBehavior.LOG,
                breaks_in_ha_version="2026.8",
                integration_domain=self.platform.platform_name,
                exclude_integrations={DOMAIN},
            )

    @callback
    def _report_deprecated_battery_feature(self) -> None:
        """Report on deprecated use of battery supported features.

        Integrations should remove the battery supported feature when migrating
        battery level and icon to a sensor.
        """
        if (
            self.platform
            and self.platform.platform_name
            not in _BATTERY_DEPRECATION_IGNORED_PLATFORMS
        ):
            # Don't report usage until after entity added to hass, after init
            report_usage(
                f"is setting the battery supported feature which has been deprecated."
                f" Integration {self.platform.platform_name} should remove this as part of migrating"
                " the battery level and icon to a sensor",
                core_behavior=ReportBehavior.LOG,
                core_integration_behavior=ReportBehavior.IGNORE,
                custom_integration_behavior=ReportBehavior.LOG,
                breaks_in_ha_version="2026.8",
                integration_domain=self.platform.platform_name,
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
            if self.__vacuum_legacy_battery_feature is False:
                self._report_deprecated_battery_feature()
                self.__vacuum_legacy_battery_feature = True
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

    async def async_get_segments(self) -> list[Segment]:
        """Get the segments that can be cleaned.

        Returns a list of segments containing their ids and names.
        """
        raise NotImplementedError

    @final
    @property
    def last_seen_segments(self) -> list[Segment] | None:
        """Return segments as seen by the user, when last mapping the areas.

        Returns None if no mapping has been saved yet.
        This can be used by integrations to detect changes in segments reported
        by the vacuum and create a repair issue.
        """
        if self.registry_entry is None:
            raise RuntimeError(
                "Cannot access last_seen_segments, registry entry is not set for"
                f" {self.entity_id}"
            )

        options: Mapping[str, Any] = self.registry_entry.options.get(DOMAIN, {})
        last_seen_segments = options.get("last_seen_segments")

        if last_seen_segments is None:
            return None

        return [Segment(**segment) for segment in last_seen_segments]

    @final
    async def async_internal_clean_area(
        self, cleaning_area_id: list[str], **kwargs: Any
    ) -> None:
        """Perform an area clean.

        Calls async_clean_segments.
        """
        if self.registry_entry is None:
            raise RuntimeError(
                "Cannot perform area clean, registry entry is not set for"
                f" {self.entity_id}"
            )

        options: Mapping[str, Any] = self.registry_entry.options.get(DOMAIN, {})
        area_mapping: dict[str, list[str]] = options.get("area_mapping", {})

        # We use a dict to preserve the order of segments.
        segment_ids: dict[str, None] = {}
        for area_id in cleaning_area_id:
            for segment_id in area_mapping.get(area_id, []):
                segment_ids[segment_id] = None

        if not segment_ids:
            _LOGGER.debug(
                "No segments found for cleaning_area_id %s on vacuum %s",
                cleaning_area_id,
                self.entity_id,
            )
            return

        await self.async_clean_segments(list(segment_ids), **kwargs)

    def clean_segments(self, segment_ids: list[str], **kwargs: Any) -> None:
        """Perform an area clean."""
        raise NotImplementedError

    async def async_clean_segments(self, segment_ids: list[str], **kwargs: Any) -> None:
        """Perform an area clean."""
        await self.hass.async_add_executor_job(
            partial(self.clean_segments, segment_ids, **kwargs)
        )

    @callback
    def async_create_segments_issue(self) -> None:
        """Create a repair issue when vacuum segments have changed.

        Integrations should call this method when the vacuum reports
        different segments than what was previously mapped to areas.

        The issue is not fixable via the standard repair flow. The frontend
        will handle the fix by showing the segment mapping dialog.
        """
        if self.registry_entry is None:
            raise RuntimeError(
                "Cannot create segments issue, registry entry is not set for"
                f" {self.entity_id}"
            )

        issue_id = f"{ISSUE_SEGMENTS_CHANGED}_{self.registry_entry.id}"
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            data={
                "entry_id": self.registry_entry.id,
                "entity_id": self.entity_id,
            },
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_SEGMENTS_CHANGED,
            translation_placeholders={
                "entity_id": self.entity_id,
            },
        )

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


@dataclass(slots=True)
class Segment:
    """Represents a cleanable segment reported by a vacuum."""

    id: str
    name: str
    group: str | None = None
