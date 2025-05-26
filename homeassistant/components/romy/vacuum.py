"""Support for Wi-Fi enabled ROMY vacuum cleaner robots.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/vacuum.romy/.
"""

from typing import Any

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, LOGGER
from .coordinator import RomyVacuumCoordinator
from .entity import RomyEntity

FAN_SPEED_NONE = "default"
FAN_SPEED_NORMAL = "normal"
FAN_SPEED_SILENT = "silent"
FAN_SPEED_INTENSIVE = "intensive"
FAN_SPEED_SUPER_SILENT = "super_silent"
FAN_SPEED_HIGH = "high"
FAN_SPEED_AUTO = "auto"

FAN_SPEEDS: list[str] = [
    FAN_SPEED_NONE,
    FAN_SPEED_NORMAL,
    FAN_SPEED_SILENT,
    FAN_SPEED_INTENSIVE,
    FAN_SPEED_SUPER_SILENT,
    FAN_SPEED_HIGH,
    FAN_SPEED_AUTO,
]

# Commonly supported features
SUPPORT_ROMY_ROBOT = (
    VacuumEntityFeature.BATTERY
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.STATE
    | VacuumEntityFeature.START
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.FAN_SPEED
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up ROMY vacuum cleaner."""

    coordinator: RomyVacuumCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([RomyVacuumEntity(coordinator)])


class RomyVacuumEntity(RomyEntity, StateVacuumEntity):
    """Representation of a ROMY vacuum cleaner robot."""

    _attr_supported_features = SUPPORT_ROMY_ROBOT
    _attr_fan_speed_list = FAN_SPEEDS
    _attr_name = None

    def __init__(
        self,
        coordinator: RomyVacuumCoordinator,
    ) -> None:
        """Initialize the ROMY Robot."""
        super().__init__(coordinator)
        self._attr_unique_id = self.romy.unique_id

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_fan_speed = FAN_SPEEDS[self.romy.fan_speed]
        self._attr_battery_level = self.romy.battery_level
        if (status := self.romy.status) is None:
            self._attr_activity = None
            self.async_write_ha_state()
            return
        try:
            self._attr_activity = VacuumActivity(status)
        except ValueError:
            self._attr_activity = None

        self.async_write_ha_state()

    async def async_start(self, **kwargs: Any) -> None:
        """Turn the vacuum on."""
        LOGGER.debug("async_start")
        await self.romy.async_clean_start_or_continue()

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        LOGGER.debug("async_stop")
        await self.romy.async_stop()

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Return vacuum back to base."""
        LOGGER.debug("async_return_to_base")
        await self.romy.async_return_to_base()

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        LOGGER.debug("async_set_fan_speed to %s", fan_speed)
        await self.romy.async_set_fan_speed(FAN_SPEEDS.index(fan_speed))
