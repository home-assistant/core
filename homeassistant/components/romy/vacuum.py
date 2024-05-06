"""Support for Wi-Fi enabled ROMY vacuum cleaner robots.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/vacuum.romy/.
"""


from typing import Any

from romy import RomyRobot

from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import RomyVacuumCoordinator

ICON = "mdi:robot-vacuum"

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
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ROMY vacuum cleaner."""

    coordinator: RomyVacuumCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([RomyVacuumEntity(coordinator, coordinator.romy)], True)


class RomyVacuumEntity(CoordinatorEntity[RomyVacuumCoordinator], StateVacuumEntity):
    """Representation of a ROMY vacuum cleaner robot."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = SUPPORT_ROMY_ROBOT
    _attr_fan_speed_list = FAN_SPEEDS
    _attr_icon = ICON

    def __init__(
        self,
        coordinator: RomyVacuumCoordinator,
        romy: RomyRobot,
    ) -> None:
        """Initialize the ROMY Robot."""
        super().__init__(coordinator)
        self.romy = romy
        self._attr_unique_id = self.romy.unique_id
        self._device_info = DeviceInfo(
            identifiers={(DOMAIN, romy.unique_id)},
            manufacturer="ROMY",
            name=romy.name,
            model=romy.model,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_fan_speed = FAN_SPEEDS[self.romy.fan_speed]
        self._attr_battery_level = self.romy.battery_level
        self._attr_state = self.romy.status

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
