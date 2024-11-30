"""Roth Touchline SL climate integration implementation for Home Assistant."""

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TouchlineSLConfigEntry
from .coordinator import TouchlineSLModuleCoordinator
from .entity import TouchlineSLZoneEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TouchlineSLConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Touchline devices."""
    coordinators = entry.runtime_data
    async_add_entities(
        TouchlineSLZone(coordinator=coordinator, zone_id=zone_id)
        for coordinator in coordinators
        for zone_id in coordinator.data.zones
    )


CONSTANT_TEMPERATURE = "constant_temperature"


class TouchlineSLZone(TouchlineSLZoneEntity, ClimateEntity):
    """Roth Touchline SL Zone."""

    _attr_hvac_action = HVACAction.IDLE
    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_name = None
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_translation_key = "zone"

    def __init__(self, coordinator: TouchlineSLModuleCoordinator, zone_id: int) -> None:
        """Construct a Touchline SL climate zone."""
        super().__init__(coordinator, zone_id)

        self._attr_unique_id = (
            f"module-{self.coordinator.data.module.id}-zone-{self.zone_id}"
        )

        # Call this in __init__ so data is populated right away, since it's
        # already available in the coordinator data.
        self.set_attr()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.set_attr()
        super()._handle_coordinator_update()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        await self.zone.set_temperature(temperature)
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Assign the zone to a particular global schedule."""
        if not self.zone:
            return

        if preset_mode == CONSTANT_TEMPERATURE and self._attr_target_temperature:
            await self.zone.set_temperature(temperature=self._attr_target_temperature)
            await self.coordinator.async_request_refresh()
            return

        if schedule := self.coordinator.data.schedules[preset_mode]:
            await self.zone.set_schedule(schedule_id=schedule.id)
            await self.coordinator.async_request_refresh()

    def set_attr(self) -> None:
        """Populate attributes with data from the coordinator."""
        schedule_names = self.coordinator.data.schedules.keys()

        self._attr_current_temperature = self.zone.temperature
        self._attr_target_temperature = self.zone.target_temperature
        self._attr_current_humidity = int(self.zone.humidity)
        self._attr_preset_modes = [*schedule_names, CONSTANT_TEMPERATURE]

        if self.zone.mode == "constantTemp":
            self._attr_preset_mode = CONSTANT_TEMPERATURE
        elif self.zone.mode == "globalSchedule":
            schedule = self.zone.schedule
            self._attr_preset_mode = schedule.name

        if self.zone.algorithm == "heating":
            self._attr_hvac_action = (
                HVACAction.HEATING if self.zone.relay_on else HVACAction.IDLE
            )
            self._attr_hvac_mode = HVACMode.HEAT
            self._attr_hvac_modes = [HVACMode.HEAT]
        elif self.zone.algorithm == "cooling":
            self._attr_hvac_action = (
                HVACAction.COOLING if self.zone.relay_on else HVACAction.IDLE
            )
            self._attr_hvac_mode = HVACMode.COOL
            self._attr_hvac_modes = [HVACMode.COOL]
