"""Select platform for IntelliClima VMC."""

from typing import override

from pyintelliclima import FanMode, FanSpeed, IntelliClimaECO2

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import IntelliClimaConfigEntry, IntelliClimaCoordinator
from .entity import IntelliClimaECOEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


FAN_MODE_TO_INTELLICLIMA_MODE = {
    "forward": FanMode.inward,
    "reverse": FanMode.outward,
    "alternate": FanMode.alternate,
    "sensor": FanMode.sensor,
}
INTELLICLIMA_MODE_TO_FAN_MODE = {v: k for k, v in FAN_MODE_TO_INTELLICLIMA_MODE.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelliClimaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up IntelliClima VMC fan mode select."""
    coordinator = entry.runtime_data.devices_coordinator

    entities: list[IntelliClimaVMCFanModeSelect] = [
        IntelliClimaVMCFanModeSelect(
            coordinator=coordinator,
            device=ecocomfort2,
        )
        for ecocomfort2 in coordinator.data.ecocomfort2_devices.values()
    ]

    async_add_entities(entities)


class IntelliClimaVMCFanModeSelect(IntelliClimaECOEntity, SelectEntity):
    """Representation of an IntelliClima VMC fan mode selector."""

    _attr_translation_key = "fan_mode"
    _attr_options = ["forward", "reverse", "alternate", "sensor"]

    def __init__(
        self,
        coordinator: IntelliClimaCoordinator,
        device: IntelliClimaECO2,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator, device)

        self._attr_unique_id = f"{device.id}_fan_mode"

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current fan mode."""
        if (fan_state := self._fan_state) is None:
            return None
        return INTELLICLIMA_MODE_TO_FAN_MODE.get(fan_state.direction)

    @override
    async def async_select_option(self, option: str) -> None:
        """Set the fan mode."""
        device_data = self._device_data

        mode = FAN_MODE_TO_INTELLICLIMA_MODE[option]

        # Determine speed: keep current speed if available, otherwise default to sleep
        if (
            device_data.speed_set == FanSpeed.auto
            or device_data.mode_set == FanMode.off
        ):
            speed = FanSpeed.sleep
        else:
            speed = device_data.speed_set

        await self.coordinator.api.ecocomfort2.set_mode_speed(
            self._device_sn, mode, speed
        )
        await self.coordinator.async_request_refresh()
