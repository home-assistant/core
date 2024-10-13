"""Platform for Husqvarna Automower base entity."""

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
import functools
import logging
from typing import TYPE_CHECKING, Any

from aioautomower.exceptions import ApiException
from aioautomower.model import MowerActivities, MowerAttributes, MowerStates, WorkArea

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AutomowerConfigEntry, AutomowerDataUpdateCoordinator
from .const import DOMAIN, EXECUTION_TIME_DELAY

_LOGGER = logging.getLogger(__name__)

ERROR_ACTIVITIES = (
    MowerActivities.STOPPED_IN_GARDEN,
    MowerActivities.UNKNOWN,
    MowerActivities.NOT_APPLICABLE,
)
ERROR_STATES = [
    MowerStates.FATAL_ERROR,
    MowerStates.ERROR,
    MowerStates.ERROR_AT_POWER_UP,
    MowerStates.NOT_APPLICABLE,
    MowerStates.UNKNOWN,
    MowerStates.STOPPED,
    MowerStates.OFF,
]


@callback
def _check_error_free(mower_attributes: MowerAttributes) -> bool:
    """Check if the mower has any errors."""
    return (
        mower_attributes.mower.state not in ERROR_STATES
        or mower_attributes.mower.activity not in ERROR_ACTIVITIES
    )


@callback
def _work_area_translation_key(work_area_id: int, key: str) -> str:
    """Return the translation key."""
    if work_area_id == 0:
        return f"my_lawn_{key}"
    return f"work_area_{key}"


@callback
def async_remove_work_area_entities(
    hass: HomeAssistant,
    coordinator: AutomowerDataUpdateCoordinator,
    entry: AutomowerConfigEntry,
    mower_id: str,
) -> None:
    """Remove deleted work areas from Home Assistant."""
    entity_reg = er.async_get(hass)
    active_work_areas = set()
    _work_areas = coordinator.data[mower_id].work_areas
    if _work_areas is not None:
        for work_area_id in _work_areas:
            uid = f"{mower_id}_{work_area_id}_cutting_height_work_area"
            active_work_areas.add(uid)
    for entity_entry in er.async_entries_for_config_entry(entity_reg, entry.entry_id):
        if (
            (split := entity_entry.unique_id.split("_"))[0] == mower_id
            and split[-1] == "area"
            and entity_entry.unique_id not in active_work_areas
        ):
            entity_reg.async_remove(entity_entry.entity_id)


def handle_sending_exception(
    poll_after_sending: bool = False,
) -> Callable[
    [Callable[..., Awaitable[Any]]], Callable[..., Coroutine[Any, Any, None]]
]:
    """Handle exceptions while sending a command and optionally refresh coordinator."""

    def decorator(
        func: Callable[..., Awaitable[Any]],
    ) -> Callable[..., Coroutine[Any, Any, None]]:
        @functools.wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            try:
                await func(self, *args, **kwargs)
            except ApiException as exception:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="command_send_failed",
                    translation_placeholders={"exception": str(exception)},
                ) from exception
            else:
                if poll_after_sending:
                    # As there are no updates from the websocket for this attribute,
                    # we need to wait until the command is executed and then poll the API.
                    await asyncio.sleep(EXECUTION_TIME_DELAY)
                    await self.coordinator.async_request_refresh()

        return wrapper

    return decorator


class AutomowerBaseEntity(CoordinatorEntity[AutomowerDataUpdateCoordinator]):
    """Defining the Automower base Entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
    ) -> None:
        """Initialize AutomowerEntity."""
        super().__init__(coordinator)
        self.mower_id = mower_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mower_id)},
            manufacturer="Husqvarna",
            model=self.mower_attributes.system.model.removeprefix(
                "HUSQVARNA "
            ).removeprefix("Husqvarna "),
            name=self.mower_attributes.system.name,
            serial_number=self.mower_attributes.system.serial_number,
            suggested_area="Garden",
        )

    @property
    def mower_attributes(self) -> MowerAttributes:
        """Get the mower attributes of the current mower."""
        return self.coordinator.data[self.mower_id]


class AutomowerAvailableEntity(AutomowerBaseEntity):
    """Replies available when the mower is connected."""

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return super().available and self.mower_attributes.metadata.connected


class AutomowerControlEntity(AutomowerAvailableEntity):
    """Replies available when the mower is connected and not in error state."""

    @property
    def available(self) -> bool:
        """Return True if the device is available."""
        return super().available and _check_error_free(self.mower_attributes)


class WorkAreaAvailableEntity(AutomowerAvailableEntity):
    """Base entity for work work areas."""

    def __init__(
        self,
        mower_id: str,
        coordinator: AutomowerDataUpdateCoordinator,
        work_area_id: int,
    ) -> None:
        """Initialize AutomowerEntity."""
        super().__init__(mower_id, coordinator)
        self.work_area_id = work_area_id

    @property
    def work_areas(self) -> dict[int, WorkArea]:
        """Get the work areas from the mower attributes."""
        if TYPE_CHECKING:
            assert self.mower_attributes.work_areas is not None
        return self.mower_attributes.work_areas

    @property
    def work_area_attributes(self) -> WorkArea:
        """Get the work area attributes of the current work area."""
        return self.work_areas[self.work_area_id]

    @property
    def available(self) -> bool:
        """Return True if the work area is available and the mower has no errors."""
        return super().available and self.work_area_id in self.work_areas


class WorkAreaControlEntity(WorkAreaAvailableEntity, AutomowerControlEntity):
    """Base entity work work areas with control function."""
