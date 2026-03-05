"""Select platform for IntelliClima VMC."""

from pyintelliclima.const import FanMode, FanSpeed
from pyintelliclima.intelliclima_types import IntelliClimaECO

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
    coordinator = entry.runtime_data

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
        device: IntelliClimaECO,
    ) -> None:
        """Class initializer."""
        super().__init__(coordinator, device)

        self._attr_unique_id = f"{device.id}_fan_mode"

    @property
    def current_option(self) -> str | None:
        """Return the current fan mode."""
        device_data = self._device_data

        if device_data.mode_set == FanMode.off:
            return None

        # If in auto mode (sensor mode with auto speed), return None (handled by fan entity preset mode)
        if (
            device_data.speed_set == FanSpeed.auto
            and device_data.mode_set == FanMode.sensor
        ):
            return None

        return INTELLICLIMA_MODE_TO_FAN_MODE.get(FanMode(device_data.mode_set))

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

        await self.coordinator.api.ecocomfort.set_mode_speed(
            self._device_sn, mode, speed
        )
        await self.coordinator.async_request_refresh()
