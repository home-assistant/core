"""Support for Hydrawise sprinkler sensors."""
from __future__ import annotations

from datetime import timedelta
from typing import cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import HydrawiseDataUpdateCoordinator, HydrawiseEntity
from .hydrawiser import Hydrawiser
from .pydrawise.schema import AdvancedProgram, AdvancedWateringSettings

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="next_cycle",
        name="Next Cycle",
        device_class=SensorDeviceClass.DATE,
    ),
    SensorEntityDescription(
        key="watering_time",
        name="Watering Time",
        icon="mdi:water-pump",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_display_precision=0,
    ),
)

WATERING_TIME_ICON = "mdi:water-pump"


# This function is called as part of the __init__.async_setup_entry (via the
# hass.config_entries.async_forward_entry_setup call)
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add entities for passed config_entry in HA."""
    coordinator: HydrawiseDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    hydrawise: Hydrawiser = coordinator.api

    entities = []

    for zone in hydrawise.zones:
        for description in SENSOR_TYPES:
            entities.append(
                HydrawiseSensor(
                    coordinator=coordinator,
                    controller_id=zone.controller_id,
                    zone_id=zone.id,
                    description=description,
                )
            )

    # Add all entities to HA
    async_add_entities(entities)


class HydrawiseSensor(HydrawiseEntity, SensorEntity):
    """A sensor implementation for Hydrawise device."""

    def __init__(
        self,
        *,
        coordinator: HydrawiseDataUpdateCoordinator,
        controller_id: int,
        zone_id: int,
        description: EntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(
            coordinator=coordinator,
            controller_id=controller_id,
            zone_id=zone_id,
            description=description,
        )
        self.update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Get the latest data and updates the states."""
        super()._handle_coordinator_update()

        self.update()

    def update(self) -> None:
        """Update state."""
        zone = self.coordinator.api.get_zone(self.zone_id)
        if zone is None:
            return

        if self.entity_description.key == "watering_time":
            if zone.scheduled_runs.current_run is not None:
                self._attr_native_value = (
                    zone.scheduled_runs.current_run.remaining_time.total_seconds() / 60
                )
            elif zone.scheduled_runs.next_run is not None:
                self._attr_native_value = (
                    zone.scheduled_runs.next_run.duration.total_seconds() / 60
                )
            else:
                duration = timedelta(seconds=0)
                advanced = cast(AdvancedWateringSettings, zone.watering_settings)
                if advanced is not None:
                    program = cast(AdvancedProgram, advanced.advanced_program)
                    if program is not None:
                        duration = program.run_time_group.duration

                self._attr_native_value = duration.total_seconds() / 60

            LOGGER.debug(
                "Updating WateringTime sensor for controller %d zone %s, remaining time %ds",
                self.controller_id,
                zone.name,
                self._attr_native_value,
            )
        else:  # _sensor_type == 'next_cycle'
            if zone.scheduled_runs.current_run is not None:
                self._attr_native_value = zone.scheduled_runs.current_run.start_time
            elif zone.scheduled_runs.next_run is not None:
                self._attr_native_value = zone.scheduled_runs.next_run.start_time
            else:
                self._attr_native_value = None

            LOGGER.debug(
                "Updating NextCycle sensor for controller %s zone %s, next cycle %s",
                self.controller_id,
                zone.name,
                self._attr_native_value,
            )
