"""Support for Ecovacs Ecovacs Vacuums."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

from deebot_client.capabilities import Capabilities, DeviceType
from deebot_client.device import Device
from deebot_client.events import (
    CachedMapInfoEvent,
    FanSpeedEvent,
    RoomsEvent,
    StateEvent,
)
from deebot_client.events.map import Map
from deebot_client.models import CleanAction, CleanMode, State
import sucks

from homeassistant.components.vacuum import (
    Segment,
    StateVacuumEntity,
    StateVacuumEntityDescription,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from . import EcovacsConfigEntry
from .const import DOMAIN
from .entity import EcovacsEntity, EcovacsLegacyEntity
from .util import get_name_key

_LOGGER = logging.getLogger(__name__)
_SEGMENTS_SEPARATOR = "_"

ATTR_ERROR = "error"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EcovacsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Ecovacs vacuums."""

    controller = config_entry.runtime_data
    vacuums: list[EcovacsVacuum | EcovacsLegacyVacuum] = [
        EcovacsVacuum(device)
        for device in controller.devices
        if device.capabilities.device_type is DeviceType.VACUUM
    ]
    vacuums.extend(
        [EcovacsLegacyVacuum(device) for device in controller.legacy_devices]
    )
    _LOGGER.debug("Adding Ecovacs Vacuums to Home Assistant: %s", vacuums)
    async_add_entities(vacuums)


class EcovacsLegacyVacuum(EcovacsLegacyEntity, StateVacuumEntity):
    """Legacy Ecovacs vacuums."""

    _attr_fan_speed_list = [sucks.FAN_SPEED_NORMAL, sucks.FAN_SPEED_HIGH]
    _attr_supported_features = (
        VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.CLEAN_SPOT
        | VacuumEntityFeature.STOP
        | VacuumEntityFeature.START
        | VacuumEntityFeature.LOCATE
        | VacuumEntityFeature.STATE
        | VacuumEntityFeature.SEND_COMMAND
        | VacuumEntityFeature.FAN_SPEED
    )

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        self._event_listeners.append(
            self.device.statusEvents.subscribe(
                lambda _: self.schedule_update_ha_state()
            )
        )
        self._event_listeners.append(
            self.device.lifespanEvents.subscribe(
                lambda _: self.schedule_update_ha_state()
            )
        )
        self._event_listeners.append(self.device.errorEvents.subscribe(self.on_error))

    def on_error(self, error: str) -> None:
        """Handle an error event from the robot.

        This will not change the entity's state. If the error caused the state
        to change, that will come through as a separate on_status event
        """
        if error in ["no_error", sucks.ERROR_CODES["100"]]:
            self.error = None
        else:
            self.error = error

        self.hass.bus.fire(
            "ecovacs_error", {"entity_id": self.entity_id, "error": error}
        )
        self.schedule_update_ha_state()

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the state of the vacuum cleaner."""
        if self.error is not None:
            return VacuumActivity.ERROR

        if self.device.is_cleaning:
            return VacuumActivity.CLEANING

        if self.device.is_charging:
            return VacuumActivity.DOCKED

        if self.device.vacuum_status == sucks.CLEAN_MODE_STOP:
            return VacuumActivity.IDLE

        if self.device.vacuum_status == sucks.CHARGE_MODE_RETURNING:
            return VacuumActivity.RETURNING

        return None

    @property
    def fan_speed(self) -> str | None:
        """Return the fan speed of the vacuum cleaner."""
        return self.device.fan_speed  # type: ignore[no-any-return]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device-specific state attributes of this vacuum."""
        data: dict[str, Any] = {}
        data[ATTR_ERROR] = self.error

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
        if self.state == VacuumActivity.CLEANING:
            self.device.run(sucks.Clean(mode=self.device.clean_status, speed=fan_speed))

    def send_command(
        self,
        command: str,
        params: dict[str, Any] | list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Send a command to a vacuum cleaner."""
        self.device.run(sucks.VacBotCommand(command, params))

    async def async_raw_get_positions(
        self,
    ) -> None:
        """Get bot and chargers positions."""
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="vacuum_raw_get_positions_not_supported",
        )


_STATE_TO_VACUUM_STATE = {
    State.IDLE: VacuumActivity.IDLE,
    State.CLEANING: VacuumActivity.CLEANING,
    State.RETURNING: VacuumActivity.RETURNING,
    State.DOCKED: VacuumActivity.DOCKED,
    State.ERROR: VacuumActivity.ERROR,
    State.PAUSED: VacuumActivity.PAUSED,
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
        super().__init__(device, device.capabilities)

        self._room_event: RoomsEvent | None = None
        self._maps: dict[str, Map] = {}

        if fan_speed := self._capability.fan_speed:
            self._attr_supported_features |= VacuumEntityFeature.FAN_SPEED
            self._attr_fan_speed_list = [
                get_name_key(level) for level in fan_speed.types
            ]

        if self._capability.map and self._capability.clean.action.area:
            self._attr_supported_features |= VacuumEntityFeature.CLEAN_AREA

    async def async_added_to_hass(self) -> None:
        """Set up the event listeners now that hass is ready."""
        await super().async_added_to_hass()

        async def on_status(event: StateEvent) -> None:
            self._attr_activity = _STATE_TO_VACUUM_STATE[event.state]
            self.async_write_ha_state()

        self._subscribe(self._capability.state.event, on_status)

        if self._capability.fan_speed:

            async def on_fan_speed(event: FanSpeedEvent) -> None:
                self._attr_fan_speed = get_name_key(event.speed)
                self.async_write_ha_state()

            self._subscribe(self._capability.fan_speed.event, on_fan_speed)

        if map_caps := self._capability.map:

            async def on_rooms(event: RoomsEvent) -> None:
                self._room_event = event
                self._check_segments_changed()
                self.async_write_ha_state()

            self._subscribe(map_caps.rooms.event, on_rooms)

            async def on_map_info(event: CachedMapInfoEvent) -> None:
                self._maps = {map_obj.id: map_obj for map_obj in event.maps}
                self._check_segments_changed()

            self._subscribe(map_caps.cached_info.event, on_map_info)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return entity specific state attributes.

        Implemented by platform classes. Convention for attribute names
        is lowercase snake_case.
        """
        rooms: dict[str, Any] = {}
        if self._room_event is None:
            return rooms

        for room in self._room_event.rooms:
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
        if TYPE_CHECKING:
            assert self._capability.fan_speed
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
                translation_domain=DOMAIN,
                translation_key="vacuum_send_command_params_dict",
            )

        if command in ["spot_area", "custom_area"]:
            if params is None:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="vacuum_send_command_params_required",
                    translation_placeholders={"command": command},
                )
            if self._capability.clean.action.area is None:
                info = self._device.device_info
                name = info.get("nick", info["name"])
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="vacuum_send_command_area_not_supported",
                    translation_placeholders={"name": name},
                )

            if command == "spot_area":
                await self._device.execute_command(
                    self._capability.clean.action.area(
                        CleanMode.SPOT_AREA,
                        params["rooms"],
                        params.get("cleanings", 1),
                    )
                )
            elif command == "custom_area":
                await self._device.execute_command(
                    self._capability.clean.action.area(
                        CleanMode.CUSTOM_AREA,
                        params["coordinates"],
                        params.get("cleanings", 1),
                    )
                )
        else:
            await self._device.execute_command(
                self._capability.custom.set(command, params)
            )

    async def async_raw_get_positions(
        self,
    ) -> dict[str, Any]:
        """Get bot and chargers positions."""
        _LOGGER.debug("async_raw_get_positions")

        if not (map_cap := self._capability.map) or not (
            position_commands := map_cap.position.get
        ):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="vacuum_raw_get_positions_not_supported",
            )

        return await self._device.execute_command(position_commands[0])

    @callback
    def _check_segments_changed(self) -> None:
        """Check if segments have changed and create repair issue."""
        last_seen = self.last_seen_segments
        if last_seen is None:
            return

        last_seen_ids = {seg.id for seg in last_seen}
        current_ids = {seg.id for seg in self._get_segments()}

        if current_ids != last_seen_ids:
            self.async_create_segments_issue()

    def _get_segments(self) -> list[Segment]:
        """Get the segments that can be cleaned."""
        last_seen = self.last_seen_segments or []
        if self._room_event is None or not self._maps:
            # If we don't have the necessary information to determine segments, return the last
            # seen segments to avoid temporarily losing all segments until we get the necessary
            # information, which could cause unnecessary issues to be created
            return last_seen

        map_id = self._room_event.map_id
        if (map_obj := self._maps.get(map_id)) is None:
            _LOGGER.warning("Map ID %s not found in available maps", map_id)
            return []

        id_prefix = f"{map_id}{_SEGMENTS_SEPARATOR}"
        other_map_ids = {
            map_obj.id
            for map_obj in self._maps.values()
            if map_obj.id != self._room_event.map_id
        }
        # Include segments from the current map and any segments from other maps that were
        # previously seen, as we want to continue showing segments from other maps for
        # mapping purposes
        segments = [
            seg for seg in last_seen if _split_composite_id(seg.id)[0] in other_map_ids
        ]
        segments.extend(
            Segment(
                id=f"{id_prefix}{room.id}",
                name=room.name,
                group=map_obj.name,
            )
            for room in self._room_event.rooms
        )
        return segments

    async def async_get_segments(self) -> list[Segment]:
        """Get the segments that can be cleaned."""
        return self._get_segments()

    async def async_clean_segments(self, segment_ids: list[str], **kwargs: Any) -> None:
        """Perform an area clean.

        Only cleans segments from the currently selected map.
        """
        if not self._maps:
            _LOGGER.warning("No map information available, cannot clean segments")
            return

        valid_room_ids: list[int | float] = []
        for composite_id in segment_ids:
            map_id, segment_id = _split_composite_id(composite_id)
            if (map_obj := self._maps.get(map_id)) is None:
                _LOGGER.warning("Map ID %s not found in available maps", map_id)
                continue

            if not map_obj.using:
                room_name = next(
                    (
                        segment.name
                        for segment in self.last_seen_segments or []
                        if segment.id == composite_id
                    ),
                    "",
                )
                _LOGGER.warning(
                    'Map "%s" is not currently selected, skipping segment "%s" (%s)',
                    map_obj.name,
                    room_name,
                    segment_id,
                )
                continue

            valid_room_ids.append(int(segment_id))

        if not valid_room_ids:
            _LOGGER.warning(
                "No valid segments to clean after validation, skipping clean segments command"
            )
            return

        if TYPE_CHECKING:
            # Supported feature is only added if clean.action.area is not None
            assert self._capability.clean.action.area is not None

        await self._device.execute_command(
            self._capability.clean.action.area(
                CleanMode.SPOT_AREA,
                valid_room_ids,
                1,
            )
        )


@callback
def _split_composite_id(composite_id: str) -> tuple[str, str]:
    """Split a composite ID into its components."""
    map_id, _, segment_id = composite_id.partition(_SEGMENTS_SEPARATOR)
    return map_id, segment_id
