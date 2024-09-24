"""Husqvarna Automower lawn mower entity."""

import copy
from datetime import time, timedelta
import logging
from typing import TYPE_CHECKING, Final

from aioautomower.model import Calendar, MowerActivities, MowerStates, Tasks, WorkArea
import voluptuous as vol

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AutomowerConfigEntry
from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerAvailableEntity, handle_sending_exception

ATTR_FRIDAY: Final = "friday"
ATTR_MONDAY: Final = "monday"
ATTR_SATURDAY: Final = "saturday"
ATTR_SUNDAY: Final = "sunday"
ATTR_THURSDAY: Final = "thursday"
ATTR_TUESDAY: Final = "tuesday"
ATTR_WEDNESDAY: Final = "wednesday"
ATTR_WORK_AREA_ID: Final = "work_area_id"
ATTR_END: Final = "end"
ATTR_START: Final = "start"
ATTR_DURATION: Final = "duration"
ATTR_MODE: Final = "mode"
DOCKED_ACTIVITIES = (MowerActivities.PARKED_IN_CS, MowerActivities.CHARGING)
MOWING_ACTIVITIES = (
    MowerActivities.MOWING,
    MowerActivities.LEAVING,
)
PAUSED_STATES = [
    MowerStates.PAUSED,
    MowerStates.WAIT_UPDATING,
    MowerStates.WAIT_POWER_UP,
]
SUPPORT_STATE_SERVICES = (
    LawnMowerEntityFeature.DOCK
    | LawnMowerEntityFeature.PAUSE
    | LawnMowerEntityFeature.START_MOWING
)
MOW = "mow"
PARK = "park"
OVERRIDE_MODES = [MOW, PARK]
MANIPULATING_SCHEDULE_MODES = ["overwrite", "add", "remove"]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up lawn mower platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        AutomowerLawnMowerEntity(mower_id, coordinator) for mower_id in coordinator.data
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "override_schedule",
        {
            vol.Required("override_mode"): vol.In(OVERRIDE_MODES),
            vol.Required(ATTR_DURATION): vol.All(
                cv.time_period,
                cv.positive_timedelta,
                vol.Range(min=timedelta(minutes=1), max=timedelta(days=42)),
            ),
        },
        "async_override_schedule",
    )
    platform.async_register_entity_service(
        "override_schedule_work_area",
        {
            vol.Required(ATTR_WORK_AREA_ID): vol.Coerce(int),
            vol.Required(ATTR_DURATION): vol.All(
                cv.time_period,
                cv.positive_timedelta,
                vol.Range(min=timedelta(minutes=1), max=timedelta(days=42)),
            ),
        },
        "async_override_schedule_work_area",
    )
    platform.async_register_entity_service(
        "set_schedule",
        {
            vol.Required(ATTR_MODE): vol.In(MANIPULATING_SCHEDULE_MODES),
            vol.Required(ATTR_START): vol.All(cv.time),
            vol.Required(ATTR_END): vol.All(cv.time),
            vol.Required(ATTR_MONDAY): vol.All(cv.boolean),
            vol.Required(ATTR_TUESDAY): vol.All(cv.boolean),
            vol.Required(ATTR_WEDNESDAY): vol.All(cv.boolean),
            vol.Required(ATTR_THURSDAY): vol.All(cv.boolean),
            vol.Required(ATTR_FRIDAY): vol.All(cv.boolean),
            vol.Required(ATTR_SATURDAY): vol.All(cv.boolean),
            vol.Required(ATTR_SUNDAY): vol.All(cv.boolean),
            vol.Optional(ATTR_WORK_AREA_ID, default=None): vol.Any(
                vol.Coerce(int), None
            ),
        },
        "async_set_schedule",
    )


class AutomowerLawnMowerEntity(AutomowerAvailableEntity, LawnMowerEntity):
    """Defining each mower Entity."""

    _attr_name = None
    _attr_supported_features = SUPPORT_STATE_SERVICES

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
    ) -> None:
        """Set up HusqvarnaAutomowerEntity."""
        super().__init__(mower_id, coordinator)
        self._attr_unique_id = mower_id

    @property
    def activity(self) -> LawnMowerActivity:
        """Return the state of the mower."""
        mower_attributes = self.mower_attributes
        if mower_attributes.mower.state in PAUSED_STATES:
            return LawnMowerActivity.PAUSED
        if mower_attributes.mower.activity in MOWING_ACTIVITIES:
            return LawnMowerActivity.MOWING
        if mower_attributes.mower.activity == MowerActivities.GOING_HOME:
            return LawnMowerActivity.RETURNING
        if (mower_attributes.mower.state == "RESTRICTED") or (
            mower_attributes.mower.activity in DOCKED_ACTIVITIES
        ):
            return LawnMowerActivity.DOCKED
        return LawnMowerActivity.ERROR

    @property
    def work_areas(self) -> dict[int, WorkArea] | None:
        """Return the work areas of the mower."""
        return self.mower_attributes.work_areas

    @handle_sending_exception()
    async def async_start_mowing(self) -> None:
        """Resume schedule."""
        await self.coordinator.api.commands.resume_schedule(self.mower_id)

    @handle_sending_exception()
    async def async_pause(self) -> None:
        """Pauses the mower."""
        await self.coordinator.api.commands.pause_mowing(self.mower_id)

    @handle_sending_exception()
    async def async_dock(self) -> None:
        """Parks the mower until next schedule."""
        await self.coordinator.api.commands.park_until_next_schedule(self.mower_id)

    @handle_sending_exception()
    async def async_override_schedule(
        self, override_mode: str, duration: timedelta
    ) -> None:
        """Override the schedule with mowing or parking."""
        if override_mode == MOW:
            await self.coordinator.api.commands.start_for(self.mower_id, duration)
        if override_mode == PARK:
            await self.coordinator.api.commands.park_for(self.mower_id, duration)

    @handle_sending_exception()
    async def async_override_schedule_work_area(
        self, work_area_id: int, duration: timedelta
    ) -> None:
        """Override the schedule with a certain work area."""
        if not self.mower_attributes.capabilities.work_areas:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="work_areas_not_supported"
            )
        if TYPE_CHECKING:
            assert self.work_areas is not None
        if work_area_id not in self.work_areas:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="work_area_not_existing"
            )
        await self.coordinator.api.commands.start_in_workarea(
            self.mower_id, work_area_id, duration
        )

    @handle_sending_exception()
    async def async_set_schedule(
        self,
        mode: str,
        start: time,
        end: time,
        monday: bool,
        tuesday: bool,
        wednesday: bool,
        thursday: bool,
        friday: bool,
        saturday: bool,
        sunday: bool,
        work_area_id: int | None = None,
    ) -> None:
        """Set schedule."""
        if start >= end:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="start_after_end",
            )
        duration = timedelta(
            hours=int(end.hour) - int(start.hour),
            minutes=int(end.minute) - int(start.minute),
        )
        user_input = Calendar(
            start,
            duration,
            monday,
            tuesday,
            wednesday,
            thursday,
            friday,
            saturday,
            sunday,
            work_area_id,
        )
        new_list = []
        existing_data = copy.copy(self.coordinator.data[self.mower_id].calendar.tasks)
        _LOGGER.debug("existing_data : %s", existing_data)
        _LOGGER.debug("user_input: %s", user_input)
        if mode == "overwrite":
            new_list.append(user_input)
            tasks = Tasks(tasks=new_list)
            await self.coordinator.api.commands.set_calendar(self.mower_id, tasks)
        if mode == "add":
            for calendar_entry in existing_data:
                if calendar_entry == user_input:
                    raise ServiceValidationError(
                        translation_domain=DOMAIN,
                        translation_key="calendar_entry_already_exists",
                    )
                if work_area_id is not None:
                    if calendar_entry.work_area_id == user_input.work_area_id:
                        new_list.append(calendar_entry)
                if work_area_id is None:
                    new_list.append(calendar_entry)
            new_list.append(user_input)
            tasks = Tasks(tasks=new_list)
            await self.coordinator.api.commands.set_calendar(self.mower_id, tasks)
        if mode == "remove":
            if existing_data == []:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="calendar_entry_not_found",
                )
            calendar_entry_found = False
            for calendar_entry in existing_data:
                if calendar_entry == user_input:
                    calendar_entry_found = True
                if (
                    calendar_entry.to_dict() != user_input.to_dict()
                    and calendar_entry.work_area_id == user_input.work_area_id
                ):
                    new_list.append(calendar_entry)
            if not calendar_entry_found:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="calendar_entry_not_found",
                )
            tasks = Tasks(tasks=new_list)
            await self.coordinator.api.commands.set_calendar(self.mower_id, tasks)
