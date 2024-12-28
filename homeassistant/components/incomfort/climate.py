"""Support for an Intergas boiler via an InComfort/InTouch Lan2RF gateway."""

from __future__ import annotations

from typing import Any

from incomfortclient import Heater as InComfortHeater, Room as InComfortRoom

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import InComfortConfigEntry
from .const import DOMAIN
from .coordinator import InComfortDataCoordinator
from .entity import IncomfortEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InComfortConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up InComfort/InTouch climate devices."""
    incomfort_coordinator = entry.runtime_data
    heaters = incomfort_coordinator.data.heaters
    async_add_entities(
        InComfortClimate(incomfort_coordinator, h, r) for h in heaters for r in h.rooms
    )


class InComfortClimate(IncomfortEntity, ClimateEntity):
    """Representation of an InComfort/InTouch climate device."""

    _attr_min_temp = 5.0
    _attr_max_temp = 30.0
    _attr_name = None
    _attr_hvac_mode = HVACMode.HEAT
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: InComfortDataCoordinator,
        heater: InComfortHeater,
        room: InComfortRoom,
    ) -> None:
        """Initialize the climate device."""
        super().__init__(coordinator)

        self._heater = heater
        self._room = room

        self._attr_unique_id = f"{heater.serial_no}_{room.room_no}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Intergas",
            name=f"Thermostat {room.room_no}",
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        return {"status": self._room.status}

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        return self._room.room_temp

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the actual current HVAC action."""
        if self._heater.is_burning and self._heater.is_pumping:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def target_temperature(self) -> float | None:
        """Return the (override)temperature we try to reach.

        As we set the override, we report back the override. The actual set point is
        is returned at a later time.
        Some older thermostats return 0.0 as override, in that case we fallback to
        the actual setpoint.
        """
        return self._room.override or self._room.setpoint

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature for this zone."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        await self._room.set_override(temperature)
        await self.coordinator.async_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
