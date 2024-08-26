"""Roth Touchline SL climate integration implementation for Home Assistant."""

from typing import Any

from pytouchlinesl import Zone
from pytouchlinesl.client.models import GlobalScheduleModel

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import TouchlineSLConfigEntry
from .coordinator import TouchlineSLModuleCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TouchlineSLConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Touchline devices."""
    account = entry.runtime_data

    for module in await account.modules():
        coordinator = TouchlineSLModuleCoordinator(hass, module=module)
        await coordinator.async_config_entry_first_refresh()
        async_add_entities(
            (
                TouchlineSLZone(coordinator=coordinator, zone_id=z)
                for z in coordinator.data["zones"]
            ),
            True,
        )


CONST_TEMP_PRESET_NAME = "Constant Temperature"


class TouchlineSLZone(CoordinatorEntity, ClimateEntity):
    """Roth Touchline SL Zone."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(self, *, coordinator, zone_id: int) -> None:
        """Construct a Touchline SL climate zone."""
        super().__init__(coordinator, context=zone_id)
        self.id: int = zone_id
        self._attr_unique_id = f"touchlinesl-zone-{self.id}"
        # Call this in __init__ so data is populated right away, since it's
        # already available in the coordinator data.
        self._update_fields_from_coordinator()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_fields_from_coordinator()
        self.async_write_ha_state()

    def _update_fields_from_coordinator(self):
        """Populate attributes with data from the coordinator."""
        zone: Zone = self.coordinator.data["zones"][self.id]
        schedule_names = self.coordinator.data["schedules"].keys()

        self._zone = zone
        self._attr_name = self._zone.name
        self._attr_current_temperature = self._zone.temperature
        self._attr_target_temperature = self._zone.target_temperature
        self._attr_current_humidity = int(self._zone.humidity)
        self._attr_preset_modes = [*schedule_names, CONST_TEMP_PRESET_NAME]

        if self._zone.mode == "constantTemp":
            self._attr_preset_mode = CONST_TEMP_PRESET_NAME
        elif self._zone.mode == "globalSchedule":
            schedule = self._zone.schedule
            assert isinstance(schedule, GlobalScheduleModel)
            self._attr_preset_mode = schedule.name

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if kwargs.get(ATTR_TEMPERATURE, None):
            self._attr_target_temperature = kwargs.get(ATTR_TEMPERATURE)

        if self._zone and self._attr_target_temperature:
            await self._zone.set_temperature(self._attr_target_temperature)

        await self.coordinator.async_request_refresh()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Assign the zone to a particular global schedule."""
        if not self._zone:
            return

        if preset_mode == CONST_TEMP_PRESET_NAME and self._attr_target_temperature:
            await self._zone.set_temperature(temperature=self._attr_target_temperature)
            await self.coordinator.async_request_refresh()
            return

        if schedule := self.coordinator.data["schedules"][preset_mode]:
            await self._zone.set_schedule(schedule_id=schedule.id)
            await self.coordinator.async_request_refresh()
