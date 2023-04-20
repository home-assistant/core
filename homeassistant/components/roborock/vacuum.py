"""Support for Roborock vacuum class."""
from typing import Any

from roborock.code_mappings import (
    RoborockFanPowerCode,
    RoborockMopIntensityCode,
    RoborockMopModeCode,
    RoborockStateCode,
)
from roborock.typing import RoborockCommand
import voluptuous as vol

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DOMAIN, SERVICE_VACUUM_SET_MOP_INTENSITY, SERVICE_VACUUM_SET_MOP_MODE
from .coordinator import RoborockDataUpdateCoordinator
from .device import RoborockCoordinatedEntity
from .models import RoborockHassDeviceInfo

STATE_CODE_TO_STATE = {
    RoborockStateCode["1"]: STATE_IDLE,  # "Starting"
    RoborockStateCode["2"]: STATE_IDLE,  # "Charger disconnected"
    RoborockStateCode["3"]: STATE_IDLE,  # "Idle"
    RoborockStateCode["4"]: STATE_CLEANING,  # "Remote control active"
    RoborockStateCode["5"]: STATE_CLEANING,  # "Cleaning"
    RoborockStateCode["6"]: STATE_RETURNING,  # "Returning home"
    RoborockStateCode["7"]: STATE_CLEANING,  # "Manual mode"
    RoborockStateCode["8"]: STATE_DOCKED,  # "Charging"
    RoborockStateCode["9"]: STATE_ERROR,  # "Charging problem"
    RoborockStateCode["10"]: STATE_PAUSED,  # "Paused"
    RoborockStateCode["11"]: STATE_CLEANING,  # "Spot cleaning"
    RoborockStateCode["12"]: STATE_ERROR,  # "Error"
    RoborockStateCode["13"]: STATE_IDLE,  # "Shutting down"
    RoborockStateCode["14"]: STATE_DOCKED,  # "Updating"
    RoborockStateCode["15"]: STATE_RETURNING,  # "Docking"
    RoborockStateCode["16"]: STATE_CLEANING,  # "Going to target"
    RoborockStateCode["17"]: STATE_CLEANING,  # "Zoned cleaning"
    RoborockStateCode["18"]: STATE_CLEANING,  # "Segment cleaning"
    RoborockStateCode["22"]: STATE_DOCKED,  # "Emptying the bin" on s7+
    RoborockStateCode["23"]: STATE_DOCKED,  # "Washing the mop" on s7maxV
    RoborockStateCode["26"]: STATE_RETURNING,  # "Going to wash the mop" on s7maxV
    RoborockStateCode["100"]: STATE_DOCKED,  # "Charging complete"
    RoborockStateCode["101"]: STATE_ERROR,  # "Device offline"
}


ATTR_STATUS = "status"
ATTR_ERROR = "error"


def add_services() -> None:
    """Add the vacuum services to hass."""
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_VACUUM_SET_MOP_MODE,
        cv.make_entity_service_schema(
            {vol.Required("mop_mode"): vol.In(list(RoborockMopModeCode.values()))}
        ),
        RoborockVacuum.async_set_mop_mode.__name__,
    )
    platform.async_register_entity_service(
        SERVICE_VACUUM_SET_MOP_INTENSITY,
        cv.make_entity_service_schema(
            {
                vol.Required("mop_intensity"): vol.In(
                    list(RoborockMopIntensityCode.values())
                )
            }
        ),
        RoborockVacuum.async_set_mop_intensity.__name__,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Roborock sensor."""
    coordinator: RoborockDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    async_add_entities(
        RoborockVacuum(slugify(device_id), device_info, coordinator)
        for device_id, device_info in coordinator.devices_info.items()
    )
    add_services()


class RoborockVacuum(RoborockCoordinatedEntity, StateVacuumEntity):
    """General Representation of a Roborock vacuum."""

    _attr_icon = "mdi:robot-vacuum"
    _attr_supported_features = (
        VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.STATUS
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.CLEAN_SPOT
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
    )
    _attr_fan_speed_list = RoborockFanPowerCode.values()

    def __init__(
        self,
        unique_id: str,
        device: RoborockHassDeviceInfo,
        coordinator: RoborockDataUpdateCoordinator,
    ) -> None:
        """Initialize a vacuum."""
        StateVacuumEntity.__init__(self)
        RoborockCoordinatedEntity.__init__(self, unique_id, device, coordinator)

    @property
    def state(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        return STATE_CODE_TO_STATE.get(self._device_status.state)

    @property
    def status(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        return self._device_status.status

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum cleaner."""
        return self._device_status.battery

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self._device_status.fan_power

    @property
    def error(self) -> str | None:
        """Get the error str if an error code exists."""
        return self._device_status.error

    async def async_start(self) -> None:
        """Start the vacuum."""
        await self.send(RoborockCommand.APP_START)

    async def async_pause(self) -> None:
        """Pause the vacuum."""
        await self.send(RoborockCommand.APP_PAUSE)

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum."""
        await self.send(RoborockCommand.APP_STOP)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Send vacuum back to base."""
        await self.send(RoborockCommand.APP_CHARGE)

    async def async_clean_spot(self, **kwargs: Any) -> None:
        """Spot clean."""
        await self.send(RoborockCommand.APP_SPOT)

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate vacuum."""
        await self.send(RoborockCommand.FIND_ME)

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set vacuum fan speed."""
        await self.send(
            RoborockCommand.SET_CUSTOM_MODE,
            [k for k, v in RoborockFanPowerCode.items() if v == fan_speed],
        )
        await self.coordinator.async_request_refresh()

    async def async_start_pause(self):
        """Start, pause or resume the cleaning task."""
        if self.state == STATE_CLEANING:
            await self.async_pause()
        else:
            await self.async_start()

    async def async_set_mop_mode(self, mop_mode: str, _=None) -> None:
        """Change vacuum mop mode."""
        await self.send(
            RoborockCommand.SET_MOP_MODE,
            [k for k, v in RoborockMopModeCode.items() if v == mop_mode],
        )

    async def async_set_mop_intensity(self, mop_intensity: str, _=None):
        """Set vacuum mop intensity."""
        await self.send(
            RoborockCommand.SET_WATER_BOX_CUSTOM_MODE,
            [k for k, v in RoborockMopIntensityCode.items() if v == mop_intensity],
        )

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner."""
        await self.send(command, params)
