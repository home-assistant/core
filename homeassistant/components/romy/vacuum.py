"""Support for Wi-Fi enabled ROMY vacuum cleaner robots.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/vacuum.romy/.
"""


from collections.abc import Mapping
from typing import Any

from romy import RomyRobot

from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ICON, LOGGER
from .coordinator import RomyVacuumCoordinator

FAN_SPEED_NONE = "Default"
FAN_SPEED_NORMAL = "Normal"
FAN_SPEED_SILENT = "Silent"
FAN_SPEED_INTENSIVE = "Intensive"
FAN_SPEED_SUPER_SILENT = "Super_Silent"
FAN_SPEED_HIGH = "High"
FAN_SPEED_AUTO = "Auto"

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
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.SEND_COMMAND
    | VacuumEntityFeature.STATUS
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.TURN_OFF
    | VacuumEntityFeature.TURN_ON
    | VacuumEntityFeature.FAN_SPEED
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ROMY vacuum cleaner."""

    coordinator: RomyVacuumCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    romy: RomyRobot = coordinator.romy

    device_info = {
        "manufacturer": "ROMY",
        "model": romy.model,
        "sw_version": romy.firmware,
        "identifiers": {"serial": romy.unique_id},
    }

    romy_vacuum_entity = RomyVacuumEntity(coordinator, romy, device_info)
    entities = [romy_vacuum_entity]
    async_add_entities(entities, True)


class RomyVacuumEntity(CoordinatorEntity[RomyVacuumCoordinator], StateVacuumEntity):
    """Representation of a ROMY vacuum cleaner robot."""

    def __init__(
        self,
        coordinator: RomyVacuumCoordinator,
        romy: RomyRobot,
        device_info: dict[str, Any],
    ) -> None:
        """Initialize the ROMY Robot."""
        super().__init__(coordinator)
        self.romy = romy
        self._device_info = device_info
        self._attr_unique_id = self.romy.unique_id
        self._state_attrs: dict[str, Any] = {}

        self._is_on = False
        self._fan_speed = FAN_SPEEDS.index(FAN_SPEED_NONE)
        self._fan_speed_update = False

    @property
    def supported_features(self) -> VacuumEntityFeature:
        """Flag vacuum cleaner robot features that are supported."""
        return SUPPORT_ROMY_ROBOT

    @property
    def fan_speed(self) -> str:
        """Return the current fan speed of the vacuum cleaner."""
        return FAN_SPEEDS[self.romy.fan_speed]

    @property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return FAN_SPEEDS

    @property
    def battery_level(self) -> None | int:
        """Return the battery level of the vacuum cleaner."""
        return self.romy.battery_level

    @property
    def state(self) -> None | str:
        """Return the state/status of the vacuum cleaner."""
        return self.romy.status

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self._is_on

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self.romy.name

    @property
    def icon(self) -> str:
        """Return the icon to use for device."""
        return ICON

    @property
    def device_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes of the device."""
        return self._state_attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the vacuum on."""
        LOGGER.debug("async_turn_on")
        ret = await self.romy.async_clean_start_or_continue()
        if ret:
            self._is_on = True

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Return vacuum back to base."""
        LOGGER.debug("async_return_to_base")
        ret = await self.romy.async_return_to_base()
        if ret:
            self._is_on = False

    # turn off robot (-> sending back to docking station)
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the vacuum off (-> send it back to docking station)."""
        LOGGER.debug("async_turn_off")
        await self.async_return_to_base()

    # stop robot (-> sending back to docking station)
    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner. (-> send it back to docking station)."""
        LOGGER.debug("async_stop")
        await self.async_return_to_base()

    # pause robot (api call stop means stop robot where is is and not sending back to docking station)
    async def async_pause(self, **kwargs: Any) -> None:
        """Pause the cleaning cycle."""
        LOGGER.debug("async_pause")
        ret = await self.romy.async_stop()
        if ret:
            self._is_on = False

    async def async_start_pause(self, **kwargs: Any) -> None:
        """Pause the cleaning task or resume it."""
        LOGGER.debug("async_start_pause")
        if self.is_on:
            await self.async_pause()
        else:
            await self.async_turn_on()

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        LOGGER.debug("async_set_fan_speed to %s", fan_speed)
        await self.romy.async_set_fan_speed(FAN_SPEEDS.index(fan_speed))
