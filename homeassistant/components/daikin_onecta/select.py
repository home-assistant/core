"""Provide Daikin schedule selection entities."""

from typing import TYPE_CHECKING, override

from daikin_onecta.models import ScheduleSelection

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import SCHEDULE_DISABLED
from .coordinator import DaikinOnectaConfigEntry
from .device import DaikinOnectaDevice
from .entity import DaikinManagementPointEntity
from .entity_descriptions import SELECT_DESCRIPTIONS

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
        )

    async_add_entities(sensors)


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
        self._attr_unique_id = f"{self._device.id}_{self._embedded_id}_{self._value}"
        self.entity_description = description
        self.update_state()

    def update_state(self) -> None:
        """Refresh the available and selected schedule options."""
        self._attr_options = self.get_options()
        self._attr_current_option = self.get_current_option()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self.update_state()
        self.async_write_ha_state()

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
        return selection.current_option or next(
            (
                schedule.name
                for schedule in selection.options
                if schedule.id == selection.selected
            ),
            None,
        )

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
                    schedule.id
                    for schedule in selection.options
                    if schedule.name == option
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
        self.async_write_ha_state()

    def get_options(self) -> list[str]:
        """Return readable configured schedules."""
        selection = self.selection()
        if selection is None:
            return []
        options = [schedule.name for schedule in selection.options]
        if selection.enabled_settable:
            options.append(SCHEDULE_DISABLED)
        return options
