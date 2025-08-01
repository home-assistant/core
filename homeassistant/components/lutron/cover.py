"""Support for Lutron shades and covers."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_STOP_COVER,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN, LutronData
from .aiolip import Device, LutronController, Output
from .entity import LutronOutput
from .travelcalculator import TravelCalculator, TravelStatus

_LOGGER = logging.getLogger(__name__)

CONF_TRAVELLING_TIME_DOWN = "travelling_time_down"
CONF_TRAVELLING_TIME_UP = "travelling_time_up"
CONF_SEND_STOP_AT_ENDS = "send_stop_at_ends"
CONF_ALWAYS_CONFIDENT = "always_confident"

ATTR_UNCONFIRMED_STATE = "unconfirmed_state"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lutron cover platform.

    Adds shades from the Main Repeater associated with the config_entry as
    cover entities.
    Motors can use set_level only for closing (0) or opening(100), so we use Cover Time Based entity.
    """
    entry_data: LutronData = hass.data[DOMAIN][config_entry.entry_id]
    entities: list[CoverEntity] = []

    for device in entry_data.covers:
        if device.is_motor:
            entities.append(
                LutronCoverTimeBased(device, entry_data.controller, config_entry)
            )
        elif device.is_shade:
            entities.append(LutronCover(device, entry_data.controller, config_entry))

    async_add_entities(entities, True)


class LutronCoverTimeBased(LutronOutput, CoverEntity, RestoreEntity):
    """Representation of a Lutron motor.

    Code from the custom component https://github.com/Sdahl1234/home-assistant-custom-components-cover-rf-time-based/tree/master.
    MOTOR doesn't support level. We are using travel time to get the current state and to travel to a specific level.
    We don't use the callback with the level, because it's only 0 or 100, and we always get 100 when it stops.
    Motor should report action_numer = 17 for the travel_time, but it doesn't.
    """

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.SET_POSITION
    )
    _attr_is_closed = None
    _attr_current_cover_position = None
    _attr_assumed_state = True

    _target_position = 0

    def __init__(
        self,
        lutron_device: Device,
        controller: LutronController,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the device."""
        super().__init__(lutron_device, controller)
        self._config_entry = config_entry
        self._always_confident = False
        self._send_stop_at_ends = True
        self._assume_uncertain_position = not self._always_confident
        self._processing_known_position = False
        self._unsubscribe_auto_updater = None
        self._travel_time_down = 5
        self._travel_time_up = 5
        self._state = None

        self.tc = TravelCalculator(self._travel_time_down, self._travel_time_up)

    async def async_added_to_hass(self) -> None:  # pylint: disable=hass-missing-super-call
        """Only cover position and confidence in that matters. The rest is calculated from this attribute."""
        old_state = await self.async_get_last_state()
        _LOGGER.debug(
            "%s async_added_to_hass :: oldState %s", self._attr_name, old_state
        )
        if (
            old_state is not None
            and self.tc is not None
            and (position := old_state.attributes.get(ATTR_CURRENT_POSITION))
            is not None
        ):
            self.tc.set_position(int(position))
        if (
            old_state is not None
            and (state := old_state.attributes.get(ATTR_UNCONFIRMED_STATE)) is not None
            and not self._always_confident
        ):
            if isinstance(state, bool):
                self._assume_uncertain_position = state
            else:
                self._assume_uncertain_position = str(state) == str(True)

        travel_time_key = f"cover.{self._lutron_device.legacy_uuid}_travel_time"
        travel_time_value = self._config_entry.options.get(travel_time_key, 5)
        # Assign the values
        self._travel_time_up = int(travel_time_value)
        self._travel_time_down = int(travel_time_value)
        self.tc = TravelCalculator(self._travel_time_down, self._travel_time_up)
        self.async_write_ha_state()

    def _handle_stop(self):
        """Handle stop button press."""
        if self.tc.is_traveling():
            _LOGGER.debug("%s: _handle_stop :: button stops cover", self._attr_name)
            self.tc.stop()
            self.stop_auto_updater()

    @property
    def unconfirmed_state(self):
        """Return the assume state as a string to persist through restarts."""
        return str(self._assume_uncertain_position)

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        attr = {}
        if self._travel_time_down is not None:
            attr[CONF_TRAVELLING_TIME_DOWN] = self._travel_time_down
        if self._travel_time_up is not None:
            attr[CONF_TRAVELLING_TIME_UP] = self._travel_time_up
        attr[ATTR_UNCONFIRMED_STATE] = str(self._assume_uncertain_position)
        return attr

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self.tc.current_position()

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        return (
            self.tc.is_traveling()
            and self.tc.travel_direction == TravelStatus.DIRECTION_UP
        )

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        return (
            self.tc.is_traveling()
            and self.tc.travel_direction == TravelStatus.DIRECTION_DOWN
        )

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self.tc.is_closed()

    @property
    def assumed_state(self) -> bool:
        """Return True unless we have set position with confidence through send_know_position service."""
        return self._assume_uncertain_position

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        if ATTR_POSITION in kwargs:
            self._target_position = kwargs[ATTR_POSITION]
            _LOGGER.debug(
                "%s: async_set_cover_position: %d",
                self._attr_name,
                self._target_position,
            )
            await self.set_position(self._target_position)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Turn the device close."""
        _LOGGER.debug("%s async_close_cover", self._attr_name)
        self.tc.start_travel_down()
        self._target_position = 0

        self.start_auto_updater()
        await self._execute_device_command(self._lutron_device.start_lowering)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Turn the device open."""
        _LOGGER.debug(
            "%s: async_open_cover time: %s", self._attr_name, self._travel_time_down
        )
        self.tc.start_travel_up()
        self._target_position = 100

        self.start_auto_updater()
        await self._execute_device_command(self._lutron_device.start_raising)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Turn the device stop."""
        _LOGGER.debug("%s: async_stop_cover", self._attr_name)
        self._handle_stop()
        await self._execute_device_command(self._lutron_device.stop)

    async def set_position(self, position):
        """Move the cover to a specific position."""
        _LOGGER.debug("%s set_position", self._attr_name)
        current_position = self.tc.current_position()
        _LOGGER.debug(
            "%s set_position :: current_position: %d, new_position: %d",
            self._attr_name,
            current_position,
            position,
        )
        command = None
        if position < current_position:
            command = SERVICE_CLOSE_COVER
        elif position > current_position:
            command = SERVICE_OPEN_COVER
        if command is not None:
            self.start_auto_updater()
            self.tc.start_travel(position)
            _LOGGER.debug("%s: set_position :: command %s", self._attr_name, command)
            await self._async_handle_command(command)

    def start_auto_updater(self):
        """Start the autoupdater to update HASS while cover is moving."""
        _LOGGER.debug("%s: start_auto_updater", self._attr_name)
        if self._unsubscribe_auto_updater is None:
            _LOGGER.debug("%s: init _unsubscribe_auto_updater", self._attr_name)
            interval = timedelta(seconds=0.1)
            self._unsubscribe_auto_updater = async_track_time_interval(
                self.hass, self.auto_updater_hook, interval
            )

    @callback
    def auto_updater_hook(self, now):
        """Call for the autoupdater."""
        _LOGGER.debug("%s: auto_updater_hook", self._attr_name)
        self.async_schedule_update_ha_state()
        if self.position_reached():
            _LOGGER.debug("%s auto_updater_hook :: position_reached", self._attr_name)
            self.stop_auto_updater()
        self.hass.async_create_task(self.auto_stop_if_necessary())

    def stop_auto_updater(self):
        """Stop the autoupdater."""
        _LOGGER.debug("%s: stop_auto_updater", self._attr_name)
        if self._unsubscribe_auto_updater is not None:
            self._unsubscribe_auto_updater()
            self._unsubscribe_auto_updater = None

    def position_reached(self):
        """Return if cover has reached its final position."""
        return self.tc.position_reached()

    #  async def set_known_action(self, **kwargs):
    #     """We want to do a few things when we get a position"""
    #     action = kwargs[ATTR_ACTION]
    #     if action not in ["open", "close", "stop"]:
    #         raise ValueError("action must be one of open, close or cover.")
    #     if action == "stop":
    #         self._handle_stop()
    #         return
    #     if action == "open":
    #         self.tc.start_travel_up()
    #         self._target_position = 100
    #     if action == "close":
    #         self.tc.start_travel_down()
    #         self._target_position = 0
    #     self.start_auto_updater()

    #  async def set_known_position(self, **kwargs):
    #     """We want to do a few things when we get a position"""
    #     position = kwargs[ATTR_POSITION]
    #     confident = kwargs[ATTR_CONFIDENT] if ATTR_CONFIDENT in kwargs else False
    #     position_type = (
    #         kwargs[ATTR_POSITION_TYPE]
    #         if ATTR_POSITION_TYPE in kwargs
    #         else ATTR_POSITION_TYPE_TARGET
    #     )
    #     if position_type not in [ATTR_POSITION_TYPE_TARGET, ATTR_POSITION_TYPE_CURRENT]:
    #         raise ValueError(
    #             ATTR_POSITION_TYPE + " must be one of %s, %s",
    #             ATTR_POSITION_TYPE_TARGET,
    #             ATTR_POSITION_TYPE_CURRENT,
    #         )
    #     _LOGGER.debug(
    #         self._attr_name
    #         + ": "
    #         + "set_known_position :: position  %d, confident %s, position_type %s, self.tc.is_traveling%s",
    #         position,
    #         str(confident),
    #         position_type,
    #         str(self.tc.is_traveling()),
    #     )
    #     self._assume_uncertain_position = (
    #         not confident if not self._always_confident else False
    #     )
    #     self._processing_known_position = True
    #     if position_type == ATTR_POSITION_TYPE_TARGET:
    #         self._target_position = position
    #         position = self.current_cover_position
    #
    #     if self.tc.is_traveling():
    #         self.tc.set_position(position)
    #         self.tc.start_travel(self._target_position)
    #         self.start_auto_updater()
    #     else:
    #         if position_type == ATTR_POSITION_TYPE_TARGET:
    #             self.tc.start_travel(self._target_position)
    #             self.start_auto_updater()
    #         else:
    #             _LOGGER.debug(
    #                 self._attr_name
    #                 + ": "
    #                 + "set_known_position :: non_traveling position  %d, confident %s, position_type %s",
    #                 position,
    #                 str(confident),
    #                 position_type,
    #             )
    #             self.tc.set_position(position)

    async def auto_stop_if_necessary(self):
        """Do auto stop if necessary."""
        current_position = self.tc.current_position()
        if self.position_reached() and not self._processing_known_position:
            self.tc.stop()
            if 0 < current_position < 100:
                _LOGGER.debug(
                    "%s: auto_stop_if_necessary :: current_position between 1 and 99 :: calling stop command",
                    self._attr_name,
                )
                await self._async_handle_command(SERVICE_STOP_COVER)
            elif self._send_stop_at_ends:
                _LOGGER.debug(
                    "%s: auto_stop_if_necessary :: send_stop_at_ends :: calling stop command",
                    self._attr_name,
                )
                await self._async_handle_command(SERVICE_STOP_COVER)

    async def _async_handle_command(self, command, *args):
        """Manage cover.* triggered command. Reset assumed state and known_position processing and execute."""
        self._assume_uncertain_position = not self._always_confident
        self._processing_known_position = False
        cmd = "UNKNOWN"
        if command == "close_cover":
            cmd = "DOWN"
            self._state = False
            await self._execute_device_command(self._lutron_device.start_lowering)
        elif command == "open_cover":
            cmd = "UP"
            self._state = True
            await self._execute_device_command(self._lutron_device.start_raising)
        elif command == "stop_cover":
            cmd = "STOP"
            self._state = True
            await self._execute_device_command(self._lutron_device.stop)

        _LOGGER.debug("%s: _async_handle_command :: %s", self._attr_name, cmd)

        # Update state of entity
        self.async_write_ha_state()


class LutronCover(LutronOutput, CoverEntity):
    """Representation of a Lutron shade."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )

    _attr_is_closed: bool | None = None
    _attr_current_cover_position: int | None = None
    _attr_assumed_state = True

    def __init__(
        self,
        lutron_device: Output,
        controller: LutronController,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the device."""
        super().__init__(lutron_device, controller)
        self._config_entry = config_entry

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._execute_device_command(self._lutron_device.set_level, 0)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._execute_device_command(self._lutron_device.set_level, 100)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the shade to a specific position."""
        if ATTR_POSITION in kwargs:
            position = kwargs[ATTR_POSITION]
            await self._execute_device_command(self._lutron_device.set_level, position)

    async def _request_state(self) -> None:
        """Request the state of the cover."""
        await self._execute_device_command(self._lutron_device.get_level)

    def _update_callback(self, value: int):
        """Update the state attributes."""
        self._attr_is_closed = value < 1
        self._attr_current_cover_position = value
        self.async_write_ha_state()
        _LOGGER.debug(
            "Lutron ID: %d updated to %f", self._lutron_device.integration_id, value
        )
