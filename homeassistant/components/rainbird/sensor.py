"""Support for Rain Bird Irrigation system LNK Wi-Fi Module."""

from collections.abc import Iterable
from datetime import datetime
import logging
from typing import override

from pyrainbird.timeline import ProgramId

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import RainbirdScheduleUpdateCoordinator, RainbirdUpdateCoordinator
from .types import RainbirdConfigEntry

_LOGGER = logging.getLogger(__name__)


ZONE_RUN_TIME_SUFFIX = "-run-time"

RAIN_DELAY_ENTITY_DESCRIPTION = SensorEntityDescription(
    key="raindelay",
    translation_key="raindelay",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RainbirdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry for a Rain Bird sensor."""
    data = config_entry.runtime_data
    async_add_entities(
        [
            RainBirdSensor(
                data.coordinator,
                RAIN_DELAY_ENTITY_DESCRIPTION,
            )
        ]
    )
    # Schedule sensors are disabled by default, which needs a unique id.
    if (unique_id := data.coordinator.unique_id) is None:
        return
    async_add_entities(
        RainBirdProgramNextRunSensor(
            data.schedule_coordinator,
            unique_id,
            data.coordinator.device_info,
            program,
        )
        for program in range(data.model_info.model_info.max_programs)
    )

    added: set[tuple[int, int]] = set()

    @callback
    def _async_add_zone_run_time_sensors(pairs: Iterable[tuple[int, int]]) -> None:
        new = [pair for pair in pairs if pair not in added]
        added.update(new)
        async_add_entities(
            RainBirdZoneRunTimeSensor(
                data.schedule_coordinator,
                unique_id,
                data.coordinator.zone_device_info(zone),
                program,
                zone,
            )
            for program, zone in new
        )

    @callback
    def _async_schedule_loaded() -> None:
        """Add a sensor for each zone a program waters."""
        _async_add_zone_run_time_sensors(
            (program.program, zone.zone)
            for program in data.schedule_coordinator.data.programs
            for zone in program.durations
            if zone.zone in data.coordinator.data.zones
        )

    config_entry.async_on_unload(
        data.schedule_coordinator.async_add_schedule_callback(_async_schedule_loaded)
    )
    # Another platform may have already loaded the schedule.
    if data.schedule_coordinator.data is not None:
        _async_schedule_loaded()

    # Sensors are only known once the schedule loads, so add back the ones from
    # earlier loads. Any that are enabled then load the schedule.
    restored: list[tuple[int, int]] = []
    for entity_entry in er.async_entries_for_config_entry(
        er.async_get(hass), config_entry.entry_id
    ):
        if not entity_entry.unique_id.endswith(ZONE_RUN_TIME_SUFFIX):
            continue
        zone, _, program = (
            entity_entry.unique_id.removeprefix(f"{unique_id}-")
            .removesuffix(ZONE_RUN_TIME_SUFFIX)
            .partition("-program-")
        )
        restored.append((int(program), int(zone)))
    _async_add_zone_run_time_sensors(restored)


class RainBirdSensor(CoordinatorEntity[RainbirdUpdateCoordinator], SensorEntity):
    """A sensor implementation for Rain Bird device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: RainbirdUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the Rain Bird sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        if coordinator.unique_id is not None:
            self._attr_unique_id = f"{coordinator.unique_id}-{description.key}"
            self._attr_device_info = coordinator.device_info
        else:
            self._attr_name = (
                f"{coordinator.device_name} {description.key.capitalize()}"
            )

    @property
    @override
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data.rain_delay


class RainBirdProgramNextRunSensor(
    CoordinatorEntity[RainbirdScheduleUpdateCoordinator], SensorEntity
):
    """The next time a program is scheduled to start."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_translation_key = "program_next_run"

    def __init__(
        self,
        coordinator: RainbirdScheduleUpdateCoordinator,
        unique_id: str,
        device_info: DeviceInfo | None,
        program: int,
    ) -> None:
        """Initialize the Rain Bird program next run sensor."""
        super().__init__(coordinator)
        self._program = program
        self._unsub_run_started: CALLBACK_TYPE | None = None
        self._attr_translation_placeholders = {"program": ProgramId(program).name}
        self._attr_unique_id = f"{unique_id}-program-{program}-next-run"
        self._attr_device_info = device_info

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(self._cancel_run_started)
        self._update_next_run()

        # The schedule is only loaded once an entity that uses it is enabled.
        self.coordinator.async_load()

    @override
    @callback
    def _handle_coordinator_update(self) -> None:
        """Recompute the next run when the schedule changes."""
        self._update_next_run()
        super()._handle_coordinator_update()

    @callback
    def _handle_run_started(self, _now: datetime) -> None:
        """Move on to the following run once the current one has started."""
        self._unsub_run_started = None
        self._update_next_run()
        self.async_write_ha_state()

    @callback
    def _cancel_run_started(self) -> None:
        if self._unsub_run_started is not None:
            self._unsub_run_started()
            self._unsub_run_started = None

    @callback
    def _update_next_run(self) -> None:
        self._cancel_run_started()
        self._attr_native_value = self._next_run()
        if self._attr_native_value is not None:
            # The schedule only refreshes every 15 minutes, so advance to the
            # following run when this one starts.
            self._unsub_run_started = async_track_point_in_utc_time(
                self.hass, self._handle_run_started, self._attr_native_value
            )

    def _next_run(self) -> datetime | None:
        if (schedule := self.coordinator.data) is None:
            return None
        program = next(
            (p for p in schedule.programs if p.program == self._program), None
        )
        if program is None:
            return None
        timeline = program.timeline_tz(dt_util.get_default_time_zone())
        if (event := next(timeline.start_after(dt_util.now()), None)) is None:
            return None
        return dt_util.as_local(event.start)


class RainBirdZoneRunTimeSensor(
    CoordinatorEntity[RainbirdScheduleUpdateCoordinator], SensorEntity
):
    """How long a program waters a zone."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_translation_key = "zone_run_time"

    def __init__(
        self,
        coordinator: RainbirdScheduleUpdateCoordinator,
        unique_id: str,
        device_info: DeviceInfo | None,
        program: int,
        zone: int,
    ) -> None:
        """Initialize the Rain Bird zone run time sensor."""
        super().__init__(coordinator)
        self._program = program
        self._zone = zone
        self._attr_translation_placeholders = {"program": ProgramId(program).name}
        self._attr_unique_id = (
            f"{unique_id}-{zone}-program-{program}{ZONE_RUN_TIME_SUFFIX}"
        )
        self._attr_device_info = device_info

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # The schedule is only loaded once an entity that uses it is enabled.
        self.coordinator.async_load()

    @property
    @override
    def native_value(self) -> int | None:
        """Return the minutes the program waters the zone, or 0 if it no longer does."""
        if (schedule := self.coordinator.data) is None:
            return None
        return next(
            (
                int(zone.duration.total_seconds() // 60)
                for program in schedule.programs
                if program.program == self._program
                for zone in program.durations
                if zone.zone == self._zone
            ),
            0,
        )
