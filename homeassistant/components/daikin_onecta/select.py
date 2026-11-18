"""Provide Daikin schedule selection entities."""

from collections import Counter
from typing import TYPE_CHECKING, override

from daikin_onecta.models import ScheduleSelection

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SCHEDULE_DISABLED
from .coordinator import DaikinOnectaConfigEntry
from .device import DaikinOnectaDevice
from .entity import (
    DaikinManagementPointEntity,
    add_entities_on_coordinator_update,
    management_point_unique_id,
)

SELECT_DESCRIPTIONS = {
    "schedule": SelectEntityDescription(key="schedule", translation_key="schedule")
}

PARALLEL_UPDATES = 1

if TYPE_CHECKING:
    from .coordinator import OnectaDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin select entities."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    add_entities_on_coordinator_update(
        config_entry,
        coordinator,
        async_add_entities,
        lambda added: _create_schedule_selects(coordinator, added),
    )


def _create_schedule_selects(
    coordinator: OnectaDataUpdateCoordinator,
    added_unique_ids: set[str],
) -> list[DaikinScheduleSelect]:
    """Create schedule selects from the current cloud model."""
    sensors: list[DaikinScheduleSelect] = []
    for device in (coordinator.data or {}).values():
        sensors.extend(
            DaikinScheduleSelect(
                device,
                coordinator,
                management_point.embedded_id,
                SELECT_DESCRIPTIONS["schedule"],
                "schedule",
            )
            for management_point in device.device.management_points
            if management_point.schedule_state is not None
            and management_point_unique_id(
                device.id, management_point.embedded_id, "schedule"
            )
            not in added_unique_ids
        )

    return sensors


class DaikinScheduleSelect(DaikinManagementPointEntity, SelectEntity):
    """Daikin Schedule Select class."""

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator: OnectaDataUpdateCoordinator,
        embedded_id: str,
        description: SelectEntityDescription,
        value: str,
    ) -> None:
        """Initialize a schedule selection entity."""
        super().__init__(device, coordinator, embedded_id)
        self._value = value
        self._attr_unique_id = management_point_unique_id(
            self._device.id, self._embedded_id, self._value
        )
        self.entity_description = description
        self.update_state()

    @override
    def update_state(self) -> None:
        """Refresh the available and selected schedule options."""
        self._attr_options = self.get_options()
        self._attr_current_option = self.get_current_option()

    def selection(self) -> ScheduleSelection | None:
        """Return the schedule selection for the current schedule mode."""
        point = self._device.management_point(self._embedded_id)
        schedule = point.schedule_state if point is not None else None
        if schedule is None:
            return None
        return schedule.active_selection

    @property
    @override
    def available(self) -> bool:
        """Return whether the management point still exposes a schedule."""
        return super().available and self.selection() is not None

    def get_current_option(self) -> str | None:
        """Return the selected schedule name."""
        selection = self.selection()
        if selection is None:
            return None
        if not selection.enabled and selection.enabled_settable:
            return SCHEDULE_DISABLED
        selected_option = next(
            (
                label
                for label, schedule_id in self._schedule_options(selection)
                if schedule_id == selection.selected
            ),
            None,
        )
        return selected_option or selection.current_option

    @override
    async def async_select_option(self, option: str) -> None:
        """Select or disable a configured schedule."""
        selection = self.selection()
        if selection is None:
            self._raise_service_validation_error("schedule_selection_unavailable")
        if option not in self.get_options():
            self._raise_service_validation_error("schedule_option_unavailable")
        if option == self.get_current_option():
            return

        schedule_id = selection.selected
        if option != SCHEDULE_DISABLED:
            schedule_id = next(
                (
                    schedule_id
                    for label, schedule_id in self._schedule_options(selection)
                    if label == option
                ),
                option,
            )

        enabled = (
            option != SCHEDULE_DISABLED
            if selection.enabled_settable
            else selection.enabled
        )
        await self._async_execute_command(
            lambda client: client.schedule(
                self._device.id, self._embedded_id
            ).set_current(
                selection.mode,
                schedule_id,
                enabled=enabled,
            ),
            "schedule_select_failed",
        )
        point = self._device.management_point(self._embedded_id)
        schedule_state = point.schedule_state if point is not None else None
        if schedule_state is not None:
            schedule_state.apply_selection(
                selection.mode,
                schedule_id,
                enabled=enabled,
            )
        self.update_state()
        self.coordinator.async_update_listeners()

    def get_options(self) -> list[str]:
        """Return readable configured schedules."""
        selection = self.selection()
        if selection is None:
            return []
        options = [label for label, _ in self._schedule_options(selection)]
        if selection.enabled_settable:
            options.append(SCHEDULE_DISABLED)
        return options

    @staticmethod
    def _schedule_options(selection: ScheduleSelection) -> list[tuple[str, str]]:
        """Return unique display labels paired with their cloud schedule IDs."""
        names = [schedule.name for schedule in selection.options]
        name_counts = Counter(names)
        return [
            (
                schedule.id
                if not schedule.name or schedule.name == "undefined"
                else (
                    f"{schedule.name} ({schedule.id})"
                    if name_counts[schedule.name] > 1
                    or schedule.name == SCHEDULE_DISABLED
                    else schedule.name
                ),
                schedule.id,
            )
            for schedule in selection.options
        ]
