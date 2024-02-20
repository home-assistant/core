"""Support for Ecovacs Ecovacs Vacuums."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from deebot_client.capabilities import Capabilities
from deebot_client.device import Device
from deebot_client.events import BatteryEvent, FanSpeedEvent, RoomsEvent, StateEvent
from deebot_client.models import CleanAction, CleanMode, Room, State
import sucks

from homeassistant.components.vacuum import (
    STATE_CLEANING,
    STATE_DOCKED,
    STATE_ERROR,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RETURNING,
    StateVacuumEntity,
    StateVacuumEntityDescription,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.util import slugify

from .const import DOMAIN
from .controller import EcovacsController
from .entity import EcovacsEntity

_LOGGER = logging.getLogger(__name__)

ATTR_ERROR = "error"
ATTR_COMPONENT_PREFIX = "component_"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Ecovacs vacuums."""
    vacuums: list[EcovacsVacuum | EcovacsLegacyVacuum] = []
    controller: EcovacsController = hass.data[DOMAIN][config_entry.entry_id]
    for device in controller.legacy_devices:
        await hass.async_add_executor_job(device.connect_and_wait_until_ready)
        vacuums.append(EcovacsLegacyVacuum(device))
    for device in controller.devices:
        vacuums.append(EcovacsVacuum(device))
    _LOGGER.debug("Adding Ecovacs Vacuums to Home Assistant: %s", vacuums)
    async_add_entities(vacuums)


class EcovacsLegacyVacuum(StateVacuumEntity):
    """Legacy Ecovacs vacuums."""

    _attr_fan_speed_list = [sucks.FAN_SPEED_NORMAL, sucks.FAN_SPEED_HIGH]
    _attr_should_poll = False
    _attr_supported_features = (
        VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.CLEAN_SPOT
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.START
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.FAN_SPEED
    )

    def __init__(self, device: sucks.VacBot) -> None:
        """Initialize the Ecovacs Vacuum."""
        self.device = device
        vacuum = self.device.vacuum

        self.error: str | None = None
        self._attr_unique_id = vacuum["did"]
        self._attr_name = vacuum.get("nick", vacuum["did"])

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        self.device.statusEvents.subscribe(lambda _: self.schedule_update_ha_state())
        self.device.batteryEvents.subscribe(lambda _: self.schedule_update_ha_state())
        self.device.lifespanEvents.subscribe(lambda _: self.schedule_update_ha_state())
        self.device.errorEvents.subscribe(self.on_error)

    def on_error(self, error: str) -> None:
        """Handle an error event from the robot.

        This will not change the entity's state. If the error caused the state
        to change, that will come through as a separate on_status event
        """
        if error == "no_error":
            self.error = None
        else:
            self.error = error

        self.hass.bus.fire(
            "ecovacs_error", {"entity_id": self.entity_id, "error": error}
        )
        self.schedule_update_ha_state()

    @property
    def state(self) -> str | None:
        """Return the state of the vacuum cleaner."""
        if self.error is not None:
            return STATE_ERROR

        if self.device.is_cleaning:
            return STATE_CLEANING

        if self.device.is_charging:
            return STATE_DOCKED

        if self.device.vacuum_status == sucks.CLEAN_MODE_STOP:
            return STATE_IDLE

        if self.device.vacuum_status == sucks.CHARGE_MODE_RETURNING:
            return STATE_RETURNING

        return None

    @property
    def battery_level(self) -> int | None:
        """Return the battery level of the vacuum cleaner."""
        if self.device.battery_status is not None:
            return self.device.battery_status * 100  # type: ignore[no-any-return]

        return None

    @property
    def battery_icon(self) -> str:
        """Return the battery icon for the vacuum cleaner."""
        return icon_for_battery_level(
            battery_level=self.battery_level, charging=self.device.is_charging
        )

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self.device.fan_speed  # type: ignore[no-any-return]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device-specific state attributes of this vacuum."""
        data: dict[str, Any] = {}
        data[ATTR_ERROR] = self.error

        for key, val in self.device.components.items():
            attr_name = ATTR_COMPONENT_PREFIX + key
            data[attr_name] = int(val * 100)

        return data

    def return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""

        self.device.run(sucks.Charge())

    def start(self, **kwargs: Any) -> None:
        """Turn the vacuum on and start cleaning."""

        self.device.run(sucks.Clean())

    def stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""

        self.device.run(sucks.Stop())

    def clean_spot(self, **kwargs: Any) -> None:
        """Perform a spot clean-up."""

        self.device.run(sucks.Spot())

    def locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner."""

        self.device.run(sucks.PlaySound())

    def set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        if self.state == STATE_CLEANING:
            self.device.run(sucks.Clean(mode=self.device.clean_status, speed=fan_speed))

    def send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner."""
        self.device.run(sucks.VacBotCommand(command, params))


_STATE_TO_VACUUM_STATE = {
    State.IDLE: STATE_IDLE,
    State.CLEANING: STATE_CLEANING,
    State.RETURNING: STATE_RETURNING,
    State.DOCKED: STATE_DOCKED,
    State.ERROR: STATE_ERROR,
    State.PAUSED: STATE_PAUSED,
}

_ATTR_ROOMS = "rooms"


class EcovacsVacuum(
    EcovacsEntity[Capabilities],
    StateVacuumEntity,
):
    """Ecovacs vacuum."""

    _unrecorded_attributes = frozenset({_ATTR_ROOMS})

    _attr_supported_features = (
        VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.START
    )

    entity_description = StateVacuumEntityDescription(
        key="vacuum", translation_key="vacuum", name=None
    )

    def __init__(self, device: Device) -> None:
        """Initialize the vacuum."""
        capabilities = device.capabilities
        super().__init__(device, capabilities)

        self._rooms: list[Room] = []

        self._attr_fan_speed_list = [
            level.display_name for level in capabilities.fan_speed.types
        ]

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_battery(event: BatteryEvent) -> None:
            self._attr_battery_level = event.value
            self.async_write_ha_state()

        async def on_fan_speed(event: FanSpeedEvent) -> None:
            self._attr_fan_speed = event.speed.display_name
            self.async_write_ha_state()

        async def on_rooms(event: RoomsEvent) -> None:
            self._rooms = event.rooms
            self.async_write_ha_state()

        async def on_status(event: StateEvent) -> None:
            self._attr_state = _STATE_TO_VACUUM_STATE[event.state]
            self.async_write_ha_state()

        self._subscribe(self._capability.battery.event, on_battery)
        self._subscribe(self._capability.fan_speed.event, on_fan_speed)
        self._subscribe(self._capability.state.event, on_status)

        if map_caps := self._capability.map:
            self._subscribe(map_caps.rooms.event, on_rooms)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes.

        Implemented by platform classes. Convention for attribute names
        is lowercase snake_case.
        """
        rooms: dict[str, Any] = {}
        for room in self._rooms:
            # convert room name to snake_case to meet the convention
            room_name = slugify(room.name)
            room_values = rooms.get(room_name)
            if room_values is None:
                rooms[room_name] = room.id
            elif isinstance(room_values, list):
                room_values.append(room.id)
            else:
                # Convert from int to list
                rooms[room_name] = [room_values, room.id]

        return {
            _ATTR_ROOMS: rooms,
        }

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        await self._device.execute_command(self._capability.fan_speed.set(fan_speed))

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        await self._device.execute_command(self._capability.charge.execute())

    async def async_stop(self, **kwargs: Any) -> None:
        """Stop the vacuum cleaner."""
        await self._clean_command(CleanAction.STOP)

    async def async_pause(self) -> None:
        """Pause the vacuum cleaner."""
        await self._clean_command(CleanAction.PAUSE)

    async def async_start(self) -> None:
        """Start the vacuum cleaner."""
        await self._clean_command(CleanAction.START)

    async def _clean_command(self, action: CleanAction) -> None:
        await self._device.execute_command(
            self._capability.clean.action.command(action)
        )

    async def async_locate(self, **kwargs: Any) -> None:
        """Locate the vacuum cleaner."""
        await self._device.execute_command(self._capability.play_sound.execute())

    async def async_send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner."""
        _LOGGER.debug("async_send_command %s with %s", command, params)
        if params is None:
            params = {}
        elif isinstance(params, list):
            raise ServiceValidationError(
                "Params must be a dict!",
                translation_domain=DOMAIN,
                translation_key="vacuum_send_command_params_dict",
            )

        if command in ["spot_area", "custom_area"]:
            if params is None:
                raise ServiceValidationError(
                    f"Params are required for {command}!",
                    translation_domain=DOMAIN,
                    translation_key="vacuum_send_command_params_required",
                    translation_placeholders={"command": command},
                )

            if command in "spot_area":
                await self._device.execute_command(
                    self._capability.clean.action.area(
                        CleanMode.SPOT_AREA,
                        str(params["rooms"]),
                        params.get("cleanings", 1),
                    )
                )
            elif command == "custom_area":
                await self._device.execute_command(
                    self._capability.clean.action.area(
                        CleanMode.CUSTOM_AREA,
                        str(params["coordinates"]),
                        params.get("cleanings", 1),
                    )
                )
        else:
            await self._device.execute_command(
                self._capability.custom.set(command, params)
            )
