"""Provide Daikin schedule selection entities."""

from collections import Counter
from typing import override

from daikin_onecta.models import ScheduleSelection

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DaikinOnectaConfigEntry, OnectaDataUpdateCoordinator
from .device import DaikinOnectaDevice
from .entity import (
    DaikinManagementPointEntity,
    EntityIdChecker,
    add_entities_on_coordinator_update,
    iter_management_points,
)
from .utils import management_point_unique_id

SELECT_DESCRIPTIONS = {
    "schedule": SelectEntityDescription(key="schedule", translation_key="schedule")
}

PARALLEL_UPDATES = 1
SCHEDULE_DISABLED = "home_assistant_schedule_is_disabled"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DaikinOnectaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Daikin select entities."""
    coordinator: OnectaDataUpdateCoordinator = config_entry.runtime_data
    add_entities_on_coordinator_update(
        hass,
        config_entry,
        coordinator,
        async_add_entities,
        lambda is_known: _create_schedule_selects(coordinator, is_known),
    )


def _create_schedule_selects(
    coordinator: OnectaDataUpdateCoordinator,
    is_known: EntityIdChecker,
) -> list[DaikinScheduleSelect]:
    """Create schedule selects from the current cloud model."""
    return [
        DaikinScheduleSelect(
            device,
            coordinator,
            management_point.embedded_id,
            SELECT_DESCRIPTIONS["schedule"],
        )
        for device, management_point in iter_management_points(coordinator)
        if management_point.schedule_state is not None
        and not is_known(
            Platform.SELECT,
            management_point_unique_id(
                device.id, management_point.embedded_id, "schedule"
            ),
        )
    ]


class DaikinScheduleSelect(DaikinManagementPointEntity, SelectEntity):
    """Daikin Schedule Select class."""

    def __init__(
        self,
        device: DaikinOnectaDevice,
        coordinator: OnectaDataUpdateCoordinator,
        embedded_id: str,
        description: SelectEntityDescription,
    ) -> None:
        """Initialize a schedule selection entity."""
        super().__init__(device, coordinator, embedded_id)
        self.entity_description = description
        self._attr_unique_id = management_point_unique_id(
            self._device_id, self._embedded_id, self.entity_description.key
        )
        self._cached_schedule_options: list[tuple[str, str]] = []
        self.update_state()

    @override
    def update_state(self) -> None:
        """Refresh the available and selected schedule options."""
        selection = self.selection()
        self._cached_schedule_options = (
            self._schedule_options(selection) if selection is not None else []
        )
        self._attr_options = self.get_options()
        self._attr_current_option = self.get_current_option(selection)

    def selection(self) -> ScheduleSelection | None:
        """Return the schedule selection for the current schedule mode."""
        point = self._management_point
        schedule = point.schedule_state if point is not None else None
        if schedule is None:
            return None
        return schedule.active_selection

    def _selection_is_settable(self, selection: ScheduleSelection) -> bool:
        """Return whether Daikin allows changing the selected schedule."""
        point = self._management_point
        schedule = point.schedule if point is not None else None
        if schedule is None or not schedule.settable:
            return False
        schedule_mode = schedule.value.modes.get(selection.mode)
        return (
            schedule_mode is not None
            and schedule_mode.current_schedule is not None
            and schedule_mode.current_schedule.settable
        )

    @property
    @override
    def available(self) -> bool:
        """Return whether the management point still exposes a schedule."""
        return (
            super().available
            and self.selection() is not None
            and bool(self._attr_options)
        )

    def get_current_option(self, selection: ScheduleSelection | None) -> str | None:
        """Return the selected schedule name."""
        if selection is None:
            return None
        if not selection.enabled:
            return SCHEDULE_DISABLED if selection.enabled_settable else None
        return next(
            (
                label
                for label, schedule_id in self._cached_schedule_options
                if schedule_id == selection.selected
            ),
            None,
        )

    @override
    async def async_select_option(self, option: str) -> None:
        """Select or disable a configured schedule."""
        selection = self.selection()
        if selection is None:
            self._raise_service_validation_error("schedule_selection_unavailable")
        options = self.get_options()
        if option not in options:
            self._raise_service_validation_error("schedule_selection_unavailable")
        if option == self.get_current_option(selection):
            return

        schedule_id = selection.selected
        if option != SCHEDULE_DISABLED:
            selected_schedule_id = next(
                (
                    schedule_id
                    for label, schedule_id in self._cached_schedule_options
                    if label == option
                ),
                None,
            )
            if selected_schedule_id is None:
                self._raise_service_validation_error("schedule_selection_unavailable")
            schedule_id = selected_schedule_id

        enabled = (
            option != SCHEDULE_DISABLED
            if selection.enabled_settable
            else selection.enabled
        )
        await self._async_execute_command(
            lambda client: client.schedule(
                self._device_id, self._embedded_id
            ).set_current(
                selection.mode,
                schedule_id,
                enabled=enabled,
            ),
            "schedule_select_failed",
        )
        point = self._management_point
        schedule_state = point.schedule_state if point is not None else None
        if schedule_state is not None:
            schedule_state.apply_selection(
                selection.mode,
                schedule_id,
                enabled=enabled,
            )
        self._publish_write_update()

    def get_options(self) -> list[str]:
        """Return readable configured schedules."""
        selection = self.selection()
        if selection is None or (
            not selection.enabled and not selection.enabled_settable
        ):
            return []
        schedule_options = self._cached_schedule_options
        if not self._selection_is_settable(selection):
            schedule_options = [
                (label, schedule_id)
                for label, schedule_id in schedule_options
                if schedule_id == selection.selected
            ]
        options = [label for label, _ in schedule_options]
        if selection.enabled_settable:
            options.append(SCHEDULE_DISABLED)
        return options

    @staticmethod
    def _schedule_options(selection: ScheduleSelection) -> list[tuple[str, str]]:
        """Return unique display labels paired with their cloud schedule IDs."""
        schedules = selection.options
        labels = [
            schedule.name
            if schedule.name and schedule.name != "undefined"
            else schedule.id
            for schedule in schedules
        ]
        counts = Counter(labels)
        reserved_labels = set(labels)
        used_labels: set[str] = set()
        unique_labels: list[str] = []
        for index, schedule in enumerate(schedules):
            label = labels[index]
            disambiguate = counts[label] > 1 or label == SCHEDULE_DISABLED
            candidate = f"{label} ({schedule.id})" if disambiguate else label
            suffix = 1
            while (
                candidate in used_labels
                or candidate == SCHEDULE_DISABLED
                or (disambiguate and candidate in reserved_labels)
            ):
                candidate = f"{label} ({schedule.id} {suffix})"
                suffix += 1
            used_labels.add(candidate)
            unique_labels.append(candidate)

        return list(
            zip(unique_labels, (schedule.id for schedule in schedules), strict=True)
        )
