# Shark IQ Wrapper.

from collections.abc import Iterable
from typing import Any

from .sharkiq_pypi.sharkiq import OperatingModes, PowerModes, Properties, SharkIqVacuum

from homeassistant.components.vacuum import (
    Segment,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_ROOMS, DOMAIN, ERROR_MESSAGES, LOGGER, SHARK
from .coordinator import SharkIqConfigEntry, SharkIqUpdateCoordinator, SkegoxUpdateCoordinator, SharkDevice, get_device_model
from .skegox_device import SkegoxDevice

OPERATING_STATE_MAP = {
    OperatingModes.PAUSE: VacuumActivity.PAUSED,
    OperatingModes.START: VacuumActivity.CLEANING,
    OperatingModes.STOP: VacuumActivity.IDLE,
    OperatingModes.RETURN: VacuumActivity.RETURNING,
}

# Should research 'Matrix' clean
# Speed or Action?
FAN_SPEEDS_MAP = {
    "Eco": PowerModes.ECO,
    "Normal": PowerModes.NORMAL,
    "Max": PowerModes.MAX,
}

FAN_SPEEDS_REVERSE = {v: k for k, v in FAN_SPEEDS_MAP.items()}

# Attributes to expose
ATTR_ERROR_CODE = "last_error_code"
ATTR_ERROR_MSG = "last_error_message"
ATTR_LOW_LIGHT = "low_light"
ATTR_RECHARGE_RESUME = "recharge_and_resume"

# Diagnostic attributes
ATTR_DIAGNOSTIC_OEM_MODEL = "oem_model"
ATTR_DIAGNOSTIC_PROPERTIES_COUNT = "properties_count"
ATTR_DIAGNOSTIC_IS_ONLINE = "is_online"

# Get the error text for a device.
def _get_error_text(device: SharkDevice) -> str | None:
    err = device.get_property_value(Properties.ERROR_CODE)
    if err:
        return ERROR_MESSAGES.get(err, f"Unknown error ({err})")
    return None

# Set up the Shark IQ vacuum cleaner.
async def async_setup_entry(hass: HomeAssistant, config_entry: SharkIqConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback,) -> None:
    coordinator = config_entry.runtime_data
    devices: Iterable[SharkDevice] = coordinator.shark_vacs.values()
    device_names = [d.name for d in devices]
    LOGGER.debug("Found %d Shark IQ device(s): %s", len(device_names), ", ".join(device_names),)
    async_add_entities([SharkVacuumEntity(d, coordinator) for d in devices])

# Shark IQ vacuum entity.
class SharkVacuumEntity(CoordinatorEntity, StateVacuumEntity):
    _coordinator: SharkIqUpdateCoordinator | SkegoxUpdateCoordinator

    _attr_fan_speed_list = list(FAN_SPEEDS_MAP)
    _attr_has_entity_name = True
    _attr_name = None  # Use device name directly; no suffix
    _attr_supported_features = (
        VacuumEntityFeature.CLEAN_AREA
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.MAP
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.LOCATE
    )
    _unrecorded_attributes = frozenset({ATTR_ROOMS})

    # Create a new SharkVacuumEntity.
    def __init__(self, sharkiq: SharkDevice, coordinator: SharkIqUpdateCoordinator | SkegoxUpdateCoordinator) -> None:
        super().__init__(coordinator)
        self.sharkiq = sharkiq
        self._attr_unique_id = sharkiq.serial_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sharkiq.serial_number)},
            manufacturer=SHARK,
            model=get_device_model(sharkiq),
            name=sharkiq.name,
            sw_version=sharkiq.get_property_value(Properties.ROBOT_FIRMWARE_VERSION),
        )

    # Tell us if the device is online.
    @property
    def is_online(self) -> bool:
        return self.coordinator.device_is_online(self.sharkiq.serial_number)

    # Return the last observed error code (or None).
    @property
    def error_code(self) -> int | None:
        return self.sharkiq.get_property_value(Properties.ERROR_CODE)

    # Return the last observed error message (or None).
    @property
    def error_message(self) -> str | None:
        return _get_error_text(self.sharkiq)

    # Return True if vacuum set to recharge and resume cleaning.
    @property
    def recharging_to_resume(self) -> int | None:
        return self.sharkiq.get_property_value(Properties.RECHARGING_TO_RESUME)

    # Get the current vacuum state.
    # NB: Currently, we do not return an error state
    # because they can be very, very stale. In the app,
    # these are (usually) handled by showing the robot as
    # stopped and sending the user a notification.
    @property
    def activity(self) -> VacuumActivity | None:
        if self.sharkiq.get_property_value(Properties.CHARGING_STATUS):
            return VacuumActivity.DOCKED
        op_mode = self.sharkiq.get_property_value(Properties.OPERATING_MODE)
        return OPERATING_STATE_MAP.get(op_mode)

    # Determine if the sensor is available based on API results.
    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and self.is_online

    # Have the device return to base.
    async def async_return_to_base(self, **kwargs: Any) -> None:
        await self.sharkiq.async_set_operating_mode(OperatingModes.RETURN)
        await self.coordinator.async_refresh()

    # Pause the cleaning task.
    async def async_pause(self) -> None:
        await self.sharkiq.async_set_operating_mode(OperatingModes.PAUSE)
        await self.coordinator.async_refresh()

    # Start the device.
    async def async_start(self) -> None:
        await self.sharkiq.async_set_operating_mode(OperatingModes.START)
        await self.coordinator.async_refresh()

    # Stop the device.
    async def async_stop(self, **kwargs: Any) -> None:
        await self.sharkiq.async_set_operating_mode(OperatingModes.STOP)
        await self.coordinator.async_refresh()

    # Cause the device to generate a loud chirp.
    async def async_locate(self, **kwargs: Any) -> None:
        await self.sharkiq.async_find_device()

    # Clean specific rooms.
    # Validates each room against the available room list and raises on
    # the first invalid room rather than collecting all errors, matching
    # the behavior of the SharkClean app.
    async def async_clean_room(self, rooms: list[str], **kwargs: Any) -> None:
        rooms_to_clean = []
        valid_rooms = self.available_rooms or []
        for room in rooms:
            if room in valid_rooms:
                rooms_to_clean.append(room)
            else:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_room",
                    translation_placeholders={"room": room},
                )

        LOGGER.debug("Cleaning room(s): %s", rooms_to_clean)
        await self.sharkiq.async_clean_rooms(rooms_to_clean)
        await self.coordinator.async_refresh()

    # Get the segments that can be cleaned.
    async def async_get_segments(self) -> list[Segment]:
        rooms = self.available_rooms or []
        return [Segment(id=room, name=room) for room in rooms]

    # Perform an area clean using segment IDs.
    async def async_clean_segments(self, segment_ids: list[str], **kwargs: Any) -> None:
        await self.async_clean_room(segment_ids, **kwargs)

    # Return the current fan speed.
    @property
    def fan_speed(self) -> str | None:
        speed_level = self.sharkiq.get_property_value(Properties.POWER_MODE)
        return FAN_SPEEDS_REVERSE.get(speed_level)

    # Set the fan speed.
    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        await self.sharkiq.async_set_property_value(Properties.POWER_MODE, FAN_SPEEDS_MAP.get(fan_speed.capitalize()))
        await self.coordinator.async_refresh()

    # Various attributes we want to expose

    # Recharge and resume mode active.
    @property
    def recharge_resume(self) -> bool | None:
        return self.sharkiq.get_property_value(Properties.RECHARGE_RESUME)

    # Get the WiFi RSSI.
    @property
    def rssi(self) -> int | None:
        return self.sharkiq.get_property_value(Properties.RSSI)

    # Let us know if the robot is operating in low-light mode.
    @property
    def low_light(self) -> bool | None:
        return self.sharkiq.get_property_value(Properties.LOW_LIGHT_MISSION)

    # Return a list of rooms available to clean.
    # Skegox -> from parsed MARD data.
    # Ayla -> from `Robot_Room_List` property.
    @property
    def available_rooms(self) -> list[str] | None:
        if isinstance(self.sharkiq, SkegoxDevice):
            return self.sharkiq.rooms
        room_list = self.sharkiq.get_property_value(Properties.ROBOT_ROOM_LIST)
        
        # (colon-separated ``FloorID:Room1:Room2`` format).
        if room_list:
            return room_list.split(":")[1:]
        return []

    # Return a dictionary of device state attributes specific to sharkiq.
    # Note: `ATTR_ROOMS` is included here for API consumers but excluded
    # from HA's recorder via `_unrecorded_attributes` to avoid storing
    # potentially large room lists in the database.
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        props_count = len(self.sharkiq.properties_full)
        oem_model = self.sharkiq.oem_model_number
        return {
            ATTR_ERROR_CODE: self.error_code,
            ATTR_ERROR_MSG: _get_error_text(self.sharkiq),
            ATTR_LOW_LIGHT: self.low_light,
            ATTR_RECHARGE_RESUME: self.recharge_resume,
            ATTR_ROOMS: self.available_rooms,
            ATTR_DIAGNOSTIC_OEM_MODEL: oem_model,
            ATTR_DIAGNOSTIC_PROPERTIES_COUNT: props_count,
            ATTR_DIAGNOSTIC_IS_ONLINE: self.is_online,
        }