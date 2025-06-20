"""Shark IQ Wrapper."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sharkiq import OperatingModes, PowerModes, Properties, SharkIqVacuum
import voluptuous as vol

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER, SERVICE_CLEAN_ROOM, SHARK
from .coordinator import SharkIqUpdateCoordinator

OPERATING_STATE_MAP = {
    OperatingModes.PAUSE: VacuumActivity.PAUSED,
    OperatingModes.START: VacuumActivity.CLEANING,
    OperatingModes.STOP: VacuumActivity.IDLE,
    OperatingModes.RETURN: VacuumActivity.RETURNING,
}

FAN_SPEEDS_MAP = {
    "Eco": PowerModes.ECO,
    "Normal": PowerModes.NORMAL,
    "Max": PowerModes.MAX,
}

STATE_RECHARGING_TO_RESUME = "recharging_to_resume"

# Attributes to expose
ATTR_ERROR_CODE = "last_error_code"
ATTR_ERROR_MSG = "last_error_message"
ATTR_LOW_LIGHT = "low_light"
ATTR_RECHARGE_RESUME = "recharge_and_resume"
ATTR_ROOMS = "rooms"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Shark IQ vacuum cleaner."""
    coordinator: SharkIqUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    devices: Iterable[SharkIqVacuum] = coordinator.shark_vacs.values()
    device_names = [d.name for d in devices]
    LOGGER.debug(
        "Found %d Shark IQ device(s): %s",
        len(device_names),
        ", ".join([d.name for d in devices]),
    )
    async_add_entities([SharkVacuumEntity(d, coordinator) for d in devices])

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_CLEAN_ROOM,
        {
            vol.Required(ATTR_ROOMS): vol.All(
                cv.ensure_list, vol.Length(min=1), [cv.string]
            ),
        },
        "async_clean_room",
    )


class SharkVacuumEntity(CoordinatorEntity[SharkIqUpdateCoordinator], StateVacuumEntity):
    """Shark IQ vacuum entity."""

    _attr_fan_speed_list = list(FAN_SPEEDS_MAP)
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = (
        VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.LOCATE
    )
    _unrecorded_attributes = frozenset({ATTR_ROOMS})

    def __init__(
        self, sharkiq: SharkIqVacuum, coordinator: SharkIqUpdateCoordinator
    ) -> None:
        """Create a new SharkVacuumEntity."""
        super().__init__(coordinator)
        self.sharkiq = sharkiq
        self._attr_unique_id = sharkiq.serial_number
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sharkiq.serial_number)},
            manufacturer=SHARK,
            model=self.model,
            name=sharkiq.name,
            sw_version=sharkiq.get_property_value(Properties.ROBOT_FIRMWARE_VERSION),
        )

    def clean_spot(self, **kwargs: Any) -> None:
        """Clean a spot. Not yet implemented."""
        raise NotImplementedError

    def send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to the vacuum. Not yet implemented."""
        raise NotImplementedError

    @property
    def is_online(self) -> bool:
        """Tell us if the device is online."""
        return self.coordinator.device_is_online(self.sharkiq.serial_number)

    @property
    def model(self) -> str:
        """Vacuum model number."""
        if self.sharkiq.vac_model_number:
            return self.sharkiq.vac_model_number
        return self.sharkiq.oem_model_number

    @property
    def error_code(self) -> int | None:
        """Return the last observed error code (or None)."""
        return self.sharkiq.error_code

    @property
    def error_message(self) -> str | None:
        """Return the last observed error message (or None)."""
        if not self.error_code:
            return None
        return self.sharkiq.error_text

    @property
    def recharging_to_resume(self) -> int | None:
        """Return True if vacuum set to recharge and resume cleaning."""
        return self.sharkiq.get_property_value(Properties.RECHARGING_TO_RESUME)

    @property
    def activity(self) -> VacuumActivity | None:
        """Get the current vacuum state.

        NB: Currently, we do not return an error state because they can be very, very stale.
        In the app, these are (usually) handled by showing the robot as stopped and sending the
        user a notification.
        """
        if self.sharkiq.get_property_value(Properties.CHARGING_STATUS):
            return VacuumActivity.DOCKED
        op_mode = self.sharkiq.get_property_value(Properties.OPERATING_MODE)
        return OPERATING_STATE_MAP.get(op_mode)

    @property
    def available(self) -> bool:
        """Determine if the sensor is available based on API results."""
        # If the last update was successful...
        return self.coordinator.last_update_success and self.is_online

    @property
    def battery_level(self) -> int | None:
        """Get the current battery level."""
        return self.sharkiq.get_property_value(Properties.BATTERY_CAPACITY)

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Have the device return to base."""
        await self.sharkiq.async_set_operating_mode(OperatingModes.RETURN)
        await self.coordinator.async_refresh()

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        await self.sharkiq.async_set_operating_mode(OperatingModes.PAUSE)
        await self.coordinator.async_refresh()

    async def async_start(self) -> None:
        """Start the device."""
        await self.sharkiq.async_set_operating_mode(OperatingModes.START)
        await self.coordinator.async_refresh()

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the device."""
        await self.sharkiq.async_set_operating_mode(OperatingModes.STOP)
        await self.coordinator.async_refresh()

    async def async_locate(self, **kwargs: Any) -> None:
        """Cause the device to generate a loud chirp."""
        await self.sharkiq.async_find_device()

    async def async_clean_room(self, rooms: list[str], **kwargs: Any) -> None:
        """Clean specific rooms."""
        rooms_to_clean = []
        valid_rooms = self.available_rooms or []
        rooms = [room.replace("_", " ").title() for room in rooms]
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

    @property
    def fan_speed(self) -> str | None:
        """Return the current fan speed."""
        fan_speed = None
        speed_level = self.sharkiq.get_property_value(Properties.POWER_MODE)
        for k, val in FAN_SPEEDS_MAP.items():
            if val == speed_level:
                fan_speed = k
        return fan_speed

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set the fan speed."""
        await self.sharkiq.async_set_property_value(
            Properties.POWER_MODE, FAN_SPEEDS_MAP.get(fan_speed.capitalize())
        )
        await self.coordinator.async_refresh()

    # Various attributes we want to expose
    @property
    def recharge_resume(self) -> bool | None:
        """Recharge and resume mode active."""
        return self.sharkiq.get_property_value(Properties.RECHARGE_RESUME)

    @property
    def rssi(self) -> int | None:
        """Get the WiFi RSSI."""
        return self.sharkiq.get_property_value(Properties.RSSI)

    @property
    def low_light(self):
        """Let us know if the robot is operating in low-light mode."""
        return self.sharkiq.get_property_value(Properties.LOW_LIGHT_MISSION)

    @property
    def available_rooms(self) -> list | None:
        """Return a list of rooms available to clean."""
        room_list = self.sharkiq.get_property_value(Properties.ROBOT_ROOM_LIST)
        if room_list:
            return room_list.split(":")[1:]
        return []

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return a dictionary of device state attributes specific to sharkiq."""
        return {
            ATTR_ERROR_CODE: self.error_code,
            ATTR_ERROR_MSG: self.sharkiq.error_text,
            ATTR_LOW_LIGHT: self.low_light,
            ATTR_RECHARGE_RESUME: self.recharge_resume,
            ATTR_ROOMS: self.available_rooms,
        }
