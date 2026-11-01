"""Support for vacuum cleaner robots (botvacs)."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
import logging
from typing import Any, final, override

from propcache.api import cached_property

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (  # noqa: F401 # STATE_PAUSED/IDLE are API
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
from homeassistant.helpers.typing import ConfigType

from .const import (  # noqa: F401
    ATTR_FAN_SPEED,
    ATTR_PARAMS,
    DATA_COMPONENT,
    DOMAIN,
    SERVICE_CLEAN_AREA,
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    VacuumActivity,
    VacuumEntityCapabilityAttribute,
    VacuumEntityFeature,
    VacuumEntityStateAttribute,
)
from .services import async_setup_services
from .websocket import async_register_websocket_handlers

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = timedelta(seconds=20)

ATTR_CLEANED_AREA = "cleaned_area"
ATTR_FAN_SPEED_LIST = "fan_speed_list"
ATTR_STATUS = "status"

SERVICE_START_PAUSE = "start_pause"

DEFAULT_NAME = "Vacuum cleaner robot"

ISSUE_SEGMENTS_CHANGED = "segments_changed"


# mypy: disallow-any-generics


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

    async_setup_services(hass)

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
    "fan_speed",
    "fan_speed_list",
    "activity",
}


class StateVacuumEntity(
    Entity, cached_properties=STATE_VACUUM_CACHED_PROPERTIES_WITH_ATTR_
):
    """Representation of a vacuum cleaner robot that supports states."""

    entity_description: StateVacuumEntityDescription

    _entity_component_unrecorded_attributes = frozenset(
        {VacuumEntityCapabilityAttribute.FAN_SPEED_LIST}
    )

    _attr_fan_speed: str | None = None
    _attr_fan_speed_list: list[str]
    _attr_activity: VacuumActivity | None = None
    _attr_supported_features: VacuumEntityFeature = VacuumEntityFeature(0)

    _segments_not_configured_issue_created: bool = False
    _segments_changed_last_seen: list[dict[str, Any]] | None = None

    @callback
    @override
    def async_registry_entry_updated(self) -> None:
        """Run when the entity registry entry has been updated."""
        self._async_check_segments_issues()

    @property
    @override
    def capability_attributes(self) -> dict[str, Any] | None:
        """Return capability attributes."""
        if VacuumEntityFeature.FAN_SPEED in self.supported_features:
            return {VacuumEntityCapabilityAttribute.FAN_SPEED_LIST: self.fan_speed_list}
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
    @override
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the vacuum cleaner."""
        data: dict[str, Any] = {}
        supported_features = self.supported_features

        if VacuumEntityFeature.FAN_SPEED in supported_features:
            data[VacuumEntityStateAttribute.FAN_SPEED] = self.fan_speed

        return data

    @final
    @property
    @override
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
    @override
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
        options: Mapping[str, Any] = self.registry_entry.options.get(DOMAIN, {})
        self._segments_changed_last_seen = options.get("last_seen_segments")

    @callback
    def _async_check_segments_issues(self) -> None:
        """Create or delete segment-related repair issues."""
        if self.registry_entry is None:
            return

        options: Mapping[str, Any] = self.registry_entry.options.get(DOMAIN, {})

        if self._segments_changed_last_seen is not None and (
            VacuumEntityFeature.CLEAN_AREA not in self.supported_features
            or options.get("last_seen_segments") != self._segments_changed_last_seen
        ):
            issue_id = f"{ISSUE_SEGMENTS_CHANGED}_{self.registry_entry.id}"
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            self._segments_changed_last_seen = None

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
