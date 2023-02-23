"""Support for Roborock vacuum class."""
from abc import ABC
import logging
import math
import time
from typing import Any

from roborock.typing import RoborockCommand, RoborockDeviceInfo, Status
import voluptuous as vol

from homeassistant.components.vacuum import (
    ATTR_BATTERY_ICON,
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
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
from homeassistant.const import ATTR_BATTERY_LEVEL, ATTR_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from . import RoborockDataUpdateCoordinator
from .const import DOMAIN
from .device import RoborockCoordinatedEntity

_LOGGER = logging.getLogger(__name__)

STATE_CODES_TO_STATUS = {
    1: "starting",
    2: "charger_disconnected",
    3: "idle",
    4: "remote_control_active",
    5: "cleaning",
    6: "returning_home",
    7: "manual_mode",
    8: "charging",
    9: "charging_problem",
    10: "paused",
    11: "spot_cleaning",
    12: "error",
    13: "shutting_down",
    14: "updating",
    15: "docking",
    16: "going_to_target",
    17: "zoned_cleaning",
    18: "segment_cleaning",
    22: "emptying_the_bin",  # on s7+, see #1189
    23: "washing_the_mop",  # on a46, #1435
    26: "going_to_wash_the_mop",  # on a46, #1435
    100: "charging_complete",
    101: "device_offline",
}

STATE_CODE_TO_STATE = {
    1: STATE_IDLE,  # "Starting"
    2: STATE_IDLE,  # "Charger disconnected"
    3: STATE_IDLE,  # "Idle"
    4: STATE_CLEANING,  # "Remote control active"
    5: STATE_CLEANING,  # "Cleaning"
    6: STATE_RETURNING,  # "Returning home"
    7: STATE_CLEANING,  # "Manual mode"
    8: STATE_DOCKED,  # "Charging"
    9: STATE_ERROR,  # "Charging problem"
    10: STATE_PAUSED,  # "Paused"
    11: STATE_CLEANING,  # "Spot cleaning"
    12: STATE_ERROR,  # "Error"
    13: STATE_IDLE,  # "Shutting down"
    14: STATE_DOCKED,  # "Updating"
    15: STATE_RETURNING,  # "Docking"
    16: STATE_CLEANING,  # "Going to target"
    17: STATE_CLEANING,  # "Zoned cleaning"
    18: STATE_CLEANING,  # "Segment cleaning"
    22: STATE_DOCKED,  # "Emptying the bin" on s7+
    23: STATE_DOCKED,  # "Washing the mop" on s7maxV
    26: STATE_RETURNING,  # "Going to wash the mop" on s7maxV
    100: STATE_DOCKED,  # "Charging complete"
    101: STATE_ERROR,  # "Device offline"
}

FAN_SPEED_CODES = {
    105: "off",
    101: "silent",
    102: "balanced",
    103: "turbo",
    104: "max",
    108: "max_plus",
    106: "custom",
}

MOP_MODE_CODES = {
    300: "standard",
    301: "deep",
    303: "deep_plus",
    302: "custom",
}

MOP_INTENSITY_CODES = {
    200: "off",
    201: "mild",
    202: "moderate",
    203: "intense",
    204: "custom",
}

ATTR_STATUS = "vacuum_status"
ATTR_MOP_MODE = "mop_mode"
ATTR_MOP_INTENSITY = "mop_intensity"
ATTR_MOP_MODE_LIST = f"{ATTR_MOP_MODE}_list"
ATTR_MOP_INTENSITY_LIST = f"{ATTR_MOP_INTENSITY}_list"
ATTR_ERROR = "error"


def add_services() -> None:
    """Add the vacuum services to hass."""
    platform = entity_platform.async_get_current_platform()

    platform.async_register_entity_service(
        "vacuum_remote_control_start",
        cv.make_entity_service_schema({}),
        RoborockVacuum.async_remote_control_start.__name__,
    )

    platform.async_register_entity_service(
        "vacuum_remote_control_stop",
        cv.make_entity_service_schema({}),
        RoborockVacuum.async_remote_control_stop.__name__,
    )

    platform.async_register_entity_service(
        "vacuum_remote_control_move",
        cv.make_entity_service_schema(
            {
                vol.Optional("velocity"): vol.All(
                    vol.Coerce(float), vol.Clamp(min=-0.29, max=0.29)
                ),
                vol.Optional("rotation"): vol.All(
                    vol.Coerce(int), vol.Clamp(min=-179, max=179)
                ),
                vol.Optional("duration"): cv.positive_int,
            }
        ),
        RoborockVacuum.async_remote_control_move.__name__,
    )

    platform.async_register_entity_service(
        "vacuum_remote_control_move_step",
        cv.make_entity_service_schema(
            {
                vol.Optional("velocity"): vol.All(
                    vol.Coerce(float), vol.Clamp(min=-0.29, max=0.29)
                ),
                vol.Optional("rotation"): vol.All(
                    vol.Coerce(int), vol.Clamp(min=-179, max=179)
                ),
                vol.Optional("duration"): cv.positive_int,
            }
        ),
        RoborockVacuum.async_remote_control_move_step.__name__,
    )

    platform.async_register_entity_service(
        "vacuum_clean_zone",
        cv.make_entity_service_schema(
            {
                vol.Required("zone"): vol.All(
                    list,
                    [
                        vol.ExactSequence(
                            [
                                vol.Coerce(int),
                                vol.Coerce(int),
                                vol.Coerce(int),
                                vol.Coerce(int),
                            ]
                        )
                    ],
                ),
                vol.Optional("repeats"): vol.All(
                    vol.Coerce(int), vol.Clamp(min=1, max=3)
                ),
            }
        ),
        RoborockVacuum.async_clean_zone.__name__,
    )

    platform.async_register_entity_service(
        "vacuum_goto",
        cv.make_entity_service_schema(
            {
                vol.Required("x_coord"): vol.Coerce(int),
                vol.Required("y_coord"): vol.Coerce(int),
            }
        ),
        RoborockVacuum.async_goto.__name__,
    )
    platform.async_register_entity_service(
        "vacuum_clean_segment",
        cv.make_entity_service_schema(
            {vol.Required("segments"): vol.Any(vol.Coerce(int), [vol.Coerce(int)])}
        ),
        RoborockVacuum.async_clean_segment.__name__,
    )
    platform.async_register_entity_service(
        "vacuum_set_mop_mode",
        cv.make_entity_service_schema(
            {vol.Required("mop_mode"): vol.In(list(MOP_MODE_CODES.values()))}
        ),
        RoborockVacuum.async_set_mop_mode.__name__,
    )
    platform.async_register_entity_service(
        "vacuum_set_mop_intensity",
        cv.make_entity_service_schema(
            {vol.Required("mop_intensity"): vol.In(list(MOP_INTENSITY_CODES.values()))}
        ),
        RoborockVacuum.async_set_mop_intensity.__name__,
    )
    platform.async_register_entity_service(
        "vacuum_set_fan_speed",
        cv.make_entity_service_schema(
            {vol.Required("fan_speed"): vol.In(list(FAN_SPEED_CODES.values()))}
        ),
        RoborockVacuum.async_set_fan_speed.__name__,
    )
    platform.async_register_entity_service(
        "vacuum_reset_consumables",
        cv.make_entity_service_schema({}),
        RoborockVacuum.async_reset_consumable.__name__,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Roborock sensor."""
    add_services()

    coordinator: RoborockDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    entities = []
    for device_id, device_info in coordinator.api.device_map.items():
        unique_id = slugify(device_id)
        entities.append(RoborockVacuum(unique_id, device_info, coordinator))
    async_add_entities(entities)


class RoborockVacuum(RoborockCoordinatedEntity, StateVacuumEntity, ABC):
    """General Representation of a Roborock sensor."""

    def __init__(
        self,
        unique_id: str,
        device: RoborockDeviceInfo,
        coordinator: RoborockDataUpdateCoordinator,
    ) -> None:
        """Initialize a sensor."""
        StateVacuumEntity.__init__(self)
        RoborockCoordinatedEntity.__init__(self, device, coordinator, unique_id)
        self.manual_seqnum = 0
        self._device = device
        self._coordinator = coordinator

    @property
    def supported_features(self) -> VacuumEntityFeature:
        """Flag vacuum cleaner features that are supported."""
        features = (
            VacuumEntityFeature.TURN_ON
            | VacuumEntityFeature.TURN_OFF
            | VacuumEntityFeature.PAUSE
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
            | VacuumEntityFeature.MAP
        )
        return features

    @property
    def icon(self) -> str:
        """Return the icon of the vacuum cleaner."""
        return "mdi:robot-vacuum"

    @property
    def translation_key(self) -> str:
        """Returns the translation key for vacuum."""
        return "roborock_vacuum"

    @property
    def state(self) -> str | None:
        """Return the status of the vacuum cleaner."""
        if not self._device_status:
            return None
        state = self._device_status.state
        return STATE_CODE_TO_STATE.get(state)

    @property
    def status(self) -> Status:
        """Return the status of the vacuum cleaner."""
        if not self._device_status:
            return
        status = self._device_status.state
        return STATE_CODES_TO_STATUS.get(status)

    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the vacuum cleaner."""
        if not self._device_status:
            return {}
        data = dict(self._device_status)

        if self.supported_features & VacuumEntityFeature.BATTERY:
            data[ATTR_BATTERY_LEVEL] = self.battery_level
            data[ATTR_BATTERY_ICON] = self.battery_icon

        if self.supported_features & VacuumEntityFeature.FAN_SPEED:
            data[ATTR_FAN_SPEED] = self.fan_speed

        data[ATTR_STATE] = self.state
        data[ATTR_STATUS] = self.status
        data[ATTR_MOP_MODE] = self.mop_mode
        data[ATTR_MOP_INTENSITY] = self.mop_intensity
        data[ATTR_ERROR] = self.error
        data.update(self.capability_attributes)

        return data

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum cleaner."""
        if not self._device_status:
            return None
        return self._device_status.battery

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        if not self._device_status:
            return None
        fan_speed = self._device_status.fan_power
        return FAN_SPEED_CODES.get(fan_speed)

    @property
    def fan_speed_list(self) -> list[str]:
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return list(FAN_SPEED_CODES.values())

    @property
    def mop_mode(self) -> str | None:
        """Return the mop mode of the vacuum cleaner."""
        if not self._device_status:
            return None
        mop_mode = self._device_status.mop_mode
        return MOP_MODE_CODES.get(mop_mode)

    @property
    def mop_mode_list(self) -> list[str]:
        """Get the list of available mop mode steps of the vacuum cleaner."""
        return list(MOP_MODE_CODES.values())

    @property
    def mop_intensity(self) -> str | None:
        """Return the mop intensity of the vacuum cleaner."""
        if not self._device_status:
            return None
        mop_intensity = self._device_status.water_box_mode
        return MOP_INTENSITY_CODES.get(mop_intensity)

    @property
    def mop_intensity_list(self) -> list[str]:
        """Get the list of available mop intensity steps of the vacuum cleaner."""
        return list(MOP_INTENSITY_CODES.values())

    @property
    def error(self) -> str | None:
        """Get the error translated if one exist."""
        if not self._device_status:
            return None
        error_code = self._device_status.error_code
        return self.translate("state", error_code)

    @property
    def capability_attributes(self) -> dict[str, list[str]]:
        """Return capability attributes."""
        capability_attributes = {}
        if self.supported_features & VacuumEntityFeature.FAN_SPEED:
            capability_attributes[ATTR_FAN_SPEED_LIST] = self.fan_speed_list
        capability_attributes[ATTR_MOP_MODE_LIST] = self.mop_mode_list
        capability_attributes[ATTR_MOP_INTENSITY_LIST] = self.mop_intensity_list
        return capability_attributes

    async def async_map(self) -> None:
        """Return map token."""
        return await self.coordinator.api.get_map_v1(self._device_id)

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
            [k for k, v in FAN_SPEED_CODES.items() if v == fan_speed],
        )
        await self.coordinator.async_request_refresh()

    async def async_set_mop_mode(self, mop_mode: str, _=None) -> None:
        """Change vacuum mop mode."""
        await self.send(
            RoborockCommand.SET_MOP_MODE,
            [k for k, v in MOP_MODE_CODES.items() if v == mop_mode],
        )
        await self.coordinator.async_request_refresh()

    async def async_set_mop_intensity(self, mop_intensity: str, _=None):
        """Set vacuum mop intensity."""
        await self.send(
            RoborockCommand.SET_WATER_BOX_CUSTOM_MODE,
            [k for k, v in MOP_INTENSITY_CODES.items() if v == mop_intensity],
        )
        await self.coordinator.async_request_refresh()

    async def async_manual_start(self):
        """Start manual control mode."""
        self.manual_seqnum = 0
        return await self.send(RoborockCommand.APP_RC_START)

    async def async_manual_stop(self):
        """Stop manual control mode."""
        self.manual_seqnum = 0
        return await self.send(RoborockCommand.APP_RC_END)

    MANUAL_ROTATION_MAX = 180
    MANUAL_ROTATION_MIN = -MANUAL_ROTATION_MAX
    MANUAL_VELOCITY_MAX = 0.3
    MANUAL_VELOCITY_MIN = -MANUAL_VELOCITY_MAX
    MANUAL_DURATION_DEFAULT = 1500

    async def async_manual_control(
        self, rotation: int, velocity: float, duration: int = MANUAL_DURATION_DEFAULT
    ):
        """Give a command over manual control interface."""
        if rotation < self.MANUAL_ROTATION_MIN or rotation > self.MANUAL_ROTATION_MAX:
            raise ValueError(
                "Given rotation is invalid, should be ]%s, %s[, was %s"
                % (self.MANUAL_ROTATION_MIN, self.MANUAL_ROTATION_MAX, rotation)
            )
        if velocity < self.MANUAL_VELOCITY_MIN or velocity > self.MANUAL_VELOCITY_MAX:
            raise ValueError(
                "Given velocity is invalid, should be ]%s, %s[, was: %s"
                % (self.MANUAL_VELOCITY_MIN, self.MANUAL_VELOCITY_MAX, velocity)
            )

        self.manual_seqnum += 1
        params = {
            "omega": round(math.radians(rotation), 1),
            "velocity": velocity,
            "duration": duration,
            "seqnum": self.manual_seqnum,
        }

        await self.send(RoborockCommand.APP_RC_MOVE, [params])

    async def async_manual_control_once(
        self, rotation: int, velocity: float, duration: int = MANUAL_DURATION_DEFAULT
    ):
        """Start the remote control mode and executes the action once before deactivating the mode."""
        number_of_tries = 3
        await self.async_manual_start()
        while number_of_tries > 0:
            if self.status.state_code == 7:
                time.sleep(5)
                await self.async_manual_control(rotation, velocity, duration)
                time.sleep(5)
                return await self.async_manual_stop()

            time.sleep(2)
            number_of_tries -= 1

    async def async_remote_control_start(self):
        """Start remote control mode."""
        await self.async_manual_start()

    async def async_remote_control_stop(self):
        """Stop remote control mode."""
        await self.async_manual_stop()

    async def async_remote_control_move(
        self, rotation: int = 0, velocity: float = 0.3, duration: int = 1500
    ):
        """Move vacuum with remote control mode."""
        await self.async_manual_control(rotation, velocity, duration)

    async def async_remote_control_move_step(
        self,
        rotation: int = 0,
        velocity: float = 0.2,
        duration: int = MANUAL_DURATION_DEFAULT,
    ):
        """Move vacuum one step with remote control mode."""
        await self.async_manual_control_once(rotation, velocity, duration)

    async def async_goto(self, x_coord: int, y_coord: int):
        """Send vacuum to x,y location."""
        await self.send(RoborockCommand.APP_GOTO_TARGET, [x_coord, y_coord])

    async def async_clean_segment(self, segments):
        """Clean the specified segments(s)."""
        if isinstance(segments, int):
            segments = [segments]

        await self.send(RoborockCommand.APP_SEGMENT_CLEAN, segments)

    async def async_clean_zone(self, zone: list, repeats: int = 1):
        """Clean selected area for the number of repeats indicated."""
        for _zone in zone:
            _zone.append(repeats)
        _LOGGER.debug("Zone with repeats: %s", zone)
        await self.send(RoborockCommand.APP_ZONED_CLEAN, zone)

    async def async_start_pause(self):
        """Pause cleaning if running."""
        if self.state == STATE_CLEANING:
            await self.async_pause()
        else:
            # Start/resume cleaning.
            await self.async_start()

    async def async_reset_consumable(self):
        """Reset the consumable data(ex. brush work time)."""
        await self.send(RoborockCommand.RESET_CONSUMABLE)
        await self.coordinator.async_request_refresh()

    async def async_send_command(
        self,
        command: RoborockCommand,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ):
        """Send a command to a vacuum cleaner."""
        return await self.send(command, params)
