"""Roth Touchline SL climate integration implementation for Home Assistant."""

from typing import Any

from pytouchlinesl import Zone

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TouchlineSLConfigEntry
from .const import DOMAIN
from .coordinator import TouchlineSLModuleCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TouchlineSLConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Touchline devices."""
    coordinators = entry.runtime_data
    for module_id in coordinators:
        async_add_entities(
            TouchlineSLZone(coordinator=coordinators[module_id], zone_id=z)
            for z in coordinators[module_id].data.zones
        )


CONST_TEMP_PRESET_NAME = "Constant Temperature"


class TouchlineSLZone(CoordinatorEntity[TouchlineSLModuleCoordinator], ClimateEntity):
    """Roth Touchline SL Zone."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(self, coordinator: TouchlineSLModuleCoordinator, zone_id: int) -> None:
        """Construct a Touchline SL climate zone."""
        super().__init__(coordinator, context=zone_id)
        self.zone_id: int = zone_id

        self._attr_name = None
        self._attr_unique_id = f"{self.zone_id}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(coordinator.data.zones[zone_id].id))},
            name=coordinator.data.zones[zone_id].name,
            manufacturer="Roth",
            via_device=(DOMAIN, coordinator.data.module.id),
            model="zone",
        )

        # Call this in __init__ so data is populated right away, since it's
        # already available in the coordinator data.
        self.set_attr()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.set_attr()
        super()._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return super().available and self.zone_id in self.coordinator.data.zones

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return

        await self._zone.set_temperature(temperature)
        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Assign the zone to a particular global schedule."""
        if not self._zone:
            return

        if preset_mode == CONST_TEMP_PRESET_NAME and self._attr_target_temperature:
            await self._zone.set_temperature(temperature=self._attr_target_temperature)
            await self.coordinator.async_request_refresh()
            return

        if schedule := self.coordinator.data.schedules[preset_mode]:
            await self._zone.set_schedule(schedule_id=schedule.id)
            await self.coordinator.async_request_refresh()

    def set_attr(self) -> None:
        """Populate attributes with data from the coordinator."""
        zone: Zone = self.coordinator.data.zones[self.zone_id]
        schedule_names = self.coordinator.data.schedules.keys()

        self._zone = zone
        self._attr_current_temperature = self._zone.temperature
        self._attr_target_temperature = self._zone.target_temperature
        self._attr_current_humidity = int(self._zone.humidity)
        self._attr_preset_modes = [*schedule_names, CONST_TEMP_PRESET_NAME]

        if self._zone.mode == "constantTemp":
            self._attr_preset_mode = CONST_TEMP_PRESET_NAME
        elif self._zone.mode == "globalSchedule":
            schedule = self._zone.schedule
            self._attr_preset_mode = schedule.name
