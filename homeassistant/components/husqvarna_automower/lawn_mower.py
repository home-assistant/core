"""Husqvarna Automower lawn mower entity."""

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from aioautomower.model import MowerActivities, MowerStates, WorkArea
import voluptuous as vol

from homeassistant.components.lawn_mower import (
    LawnMowerActivity,
    LawnMowerEntity,
    LawnMowerEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AutomowerConfigEntry
from .const import DOMAIN
from .coordinator import AutomowerDataUpdateCoordinator
from .entity import AutomowerAvailableEntity, handle_sending_exception

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 1

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AutomowerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up lawn mower platform."""
    coordinator = entry.runtime_data

    def _async_add_new_devices(mower_ids: set[str]) -> None:
        async_add_entities(
            [AutomowerLawnMowerEntity(mower_id, coordinator) for mower_id in mower_ids]
        )

    _async_add_new_devices(set(coordinator.data))

    coordinator.new_devices_callbacks.append(_async_add_new_devices)
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        "override_schedule",
        {
            vol.Required("override_mode"): vol.In(OVERRIDE_MODES),
            vol.Required("duration"): vol.All(
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
            vol.Required("work_area_id"): vol.Coerce(int),
            vol.Required("duration"): vol.All(
                cv.time_period,
                cv.positive_timedelta,
                vol.Range(min=timedelta(minutes=1), max=timedelta(days=42)),
            ),
        },
        "async_override_schedule_work_area",
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
