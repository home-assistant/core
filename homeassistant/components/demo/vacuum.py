"""Demo platform for the vacuum component."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.vacuum import (
    ATTR_CLEANED_AREA,
    Segment,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import event
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN

SUPPORT_MINIMAL_SERVICES = VacuumEntityFeature.TURN_ON | VacuumEntityFeature.TURN_OFF

SUPPORT_BASIC_SERVICES = (
    VacuumEntityFeature.STATE | VacuumEntityFeature.START | VacuumEntityFeature.STOP
)

SUPPORT_MOST_SERVICES = (
    VacuumEntityFeature.STATE
    | VacuumEntityFeature.START
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.FAN_SPEED
)

SUPPORT_ALL_SERVICES = (
    VacuumEntityFeature.STATE
    | VacuumEntityFeature.START
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.FAN_SPEED
    | VacuumEntityFeature.SEND_COMMAND
    | VacuumEntityFeature.LOCATE
    | VacuumEntityFeature.STATUS
    | VacuumEntityFeature.LOCATE
    | VacuumEntityFeature.MAP
    | VacuumEntityFeature.CLEAN_SPOT
    | VacuumEntityFeature.CLEAN_AREA
)

FAN_SPEEDS = ["min", "medium", "high", "max"]
DEMO_SEGMENTS = [
    Segment(id="living_room", name="Living room"),
    Segment(id="kitchen", name="Kitchen"),
    Segment(id="bedroom_1", name="Master bedroom", group="Bedrooms"),
    Segment(id="bedroom_2", name="Guest bedroom", group="Bedrooms"),
    Segment(id="bathroom", name="Bathroom"),
]
DEMO_VACUUM_COMPLETE = "Demo vacuum 0 ground floor"
DEMO_VACUUM_MOST = "Demo vacuum 1 first floor"
DEMO_VACUUM_BASIC = "Demo vacuum 2 second floor"
DEMO_VACUUM_MINIMAL = "Demo vacuum 3 third floor"
DEMO_VACUUM_NONE = "Demo vacuum 4 fourth floor"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    async_add_entities(
        [
            StateDemoVacuum("vacuum_1", DEMO_VACUUM_COMPLETE, SUPPORT_ALL_SERVICES),
            StateDemoVacuum("vacuum_2", DEMO_VACUUM_MOST, SUPPORT_MOST_SERVICES),
            StateDemoVacuum("vacuum_3", DEMO_VACUUM_BASIC, SUPPORT_BASIC_SERVICES),
            StateDemoVacuum("vacuum_4", DEMO_VACUUM_MINIMAL, SUPPORT_MINIMAL_SERVICES),
            StateDemoVacuum("vacuum_5", DEMO_VACUUM_NONE, VacuumEntityFeature(0)),
        ]
    )


class StateDemoVacuum(StateVacuumEntity):
    """Representation of a demo vacuum supporting states."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_translation_key = "model_s"

    def __init__(
        self, unique_id: str, name: str, supported_features: VacuumEntityFeature
    ) -> None:
        """Initialize the vacuum."""
        self._attr_unique_id = unique_id
        self._attr_supported_features = supported_features
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            name=name,
        )
        self._attr_activity = VacuumActivity.DOCKED
        self._fan_speed = FAN_SPEEDS[1]
        self._cleaned_area: float = 0

    @property
    def fan_speed(self) -> str:
        """Return the current fan speed of the vacuum."""
        return self._fan_speed

    @property
    def fan_speed_list(self) -> list[str]:
        """Return the list of supported fan speeds."""
        return FAN_SPEEDS

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return device state attributes."""
        return {ATTR_CLEANED_AREA: round(self._cleaned_area, 2)}

    def start(self) -> None:
        """Start or resume the cleaning task."""
        if self._attr_activity != VacuumActivity.CLEANING:
            self._attr_activity = VacuumActivity.CLEANING
            self._cleaned_area += 1.32
            self.schedule_update_ha_state()

    def pause(self) -> None:
        """Pause the cleaning task."""
        if self._attr_activity == VacuumActivity.CLEANING:
            self._attr_activity = VacuumActivity.PAUSED
            self.schedule_update_ha_state()

    def stop(self, **kwargs: Any) -> None:
        """Stop the cleaning task, do not return to dock."""
        self._attr_activity = VacuumActivity.IDLE
        self.schedule_update_ha_state()

    def return_to_base(self, **kwargs: Any) -> None:
        """Return dock to charging base."""
        self._attr_activity = VacuumActivity.RETURNING
        self.schedule_update_ha_state()

        event.call_later(self.hass, 30, self.__set_state_to_dock)

    def clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean-up."""
        self._attr_activity = VacuumActivity.CLEANING
        self._cleaned_area += 1.32
        self.schedule_update_ha_state()

    def set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set the vacuum's fan speed."""
        if fan_speed in self.fan_speed_list:
            self._fan_speed = fan_speed
            self.schedule_update_ha_state()

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum's position."""
        await self.hass.services.async_call(
            "notify",
            "persistent_notification",
            service_data={"message": "I'm here!", "title": "Locate request"},
        )
        self._attr_activity = VacuumActivity.IDLE
        self.async_write_ha_state()

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Locate the vacuum's position."""
        self._attr_activity = VacuumActivity.CLEANING
        self.async_write_ha_state()

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to the vacuum."""
        self._attr_activity = VacuumActivity.IDLE
        self.async_write_ha_state()

    async def async_get_segments(self) -> list[Segment]:
        """Get the list of segments."""
        return DEMO_SEGMENTS

    async def async_clean_segments(self, segment_ids: list[str], **kwargs: Any) -> None:
        """Clean the specified segments."""
        self._attr_activity = VacuumActivity.CLEANING
        self._cleaned_area += len(segment_ids) * 0.7
        self.async_write_ha_state()

    def __set_state_to_dock(self, _: datetime) -> None:
        self._attr_activity = VacuumActivity.DOCKED
        self.schedule_update_ha_state()
