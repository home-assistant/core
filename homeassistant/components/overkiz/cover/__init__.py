"""Support for Overkiz covers - shutters etc."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .. import OverkizDataConfigEntry
from .awning import Awning
from .generic_cover import OverkizGenericCover
from .vertical_cover import LowSpeedCover, VerticalCover


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OverkizDataConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Overkiz covers from a config entry."""
    data = entry.runtime_data

    for device in data.platforms[Platform.SWITCH]:
        if description := SUPPORTED_DEVICES.get(device.widget) or SUPPORTED_DEVICES.get(
            device.ui_class
        ):
            entities.append(
                OverkizCover(
                    device.device_url,
                    data.coordinator,
                    description,
                )
            )

    async_add_entities(entities)


class OverkizCover(OverkizDescriptiveEntity, CoverEntity):
    """Representation of an Overkiz Cover."""

    entity_description: OverkizCoverDescription

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""

        if is_closed_fn := self.entity_description.is_closed_fn:
            return is_closed_fn(self.device)

        # Fallback to self.current_cover_position == 0 ?

        return None

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        state_name = self.entity_description.current_position_state

        if not state_name:
            return None

        if state := self.device.states[state_name]:
            position = cast(int, state.value)

        if self.entity_description.invert_position:
            position = 100 - position

        return position

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        if self.entity_description.invert_position:
            position = 100 - position

        if command := self.entity_description.set_position_command:
            await self.executor.async_execute_command(command, position)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        if command := self.entity_description.open_command:
            await self.executor.async_execute_command(command)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        if command := self.entity_description.close_command:
            await self.executor.async_execute_command(command)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        if command := self.entity_description.stop_command:
            await self.executor.async_execute_command(command)

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current position of cover tilt.

        None is unknown, 0 is closed, 100 is fully open.
        """
        state_name = self.entity_description.current_position_state

        if not state_name:
            return None

        if state := self.device.states[state_name]:
            return cast(int, state.value)

        return None

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        position = kwargs[ATTR_TILT_POSITION]
        if command := self.entity_description.set_tilt_position_command:
            await self.executor.async_execute_command(command, position)

    async def async_open_tilt_cover(self, **kwargs: Any) -> None:
        """Open the cover tilt."""
        if command := self.entity_description.open_tilt_command:
            await self.executor.async_execute_command(command)

    async def async_close_tilt_cover(self, **kwargs: Any) -> None:
        """Close the cover tilt."""
        if command := self.entity_description.close_tilt_command:
            await self.executor.async_execute_command(command)

    async def async_stop_tilt_cover(self, **kwargs: Any) -> None:
        """Stop the cover tilt."""
        if command := self.entity_description.stop_tilt_command:
            await self.executor.async_execute_command(command)

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening or not."""

        if command := self.entity_description.open_command:
            if self.is_running(command):
                return True

        if self.moving_offset is None:
            return None

        if self.entity_description.invert_position:
            return self.moving_offset > 0
        return self.moving_offset < 0

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is opening or not."""

        if command := self.entity_description.close_command:
            if self.is_running(command):
                return True

        if self.moving_offset is None:
            return None

        if self.entity_description.invert_position:
            return self.moving_offset < 0
        return self.moving_offset > 0

    def is_running(self, command: OverkizCommand) -> bool:
        """Return if the given commands are currently running."""
        return any(
            execution.get("device_url") == self.device.device_url
            and execution.get("command_name") == command
            for execution in self.coordinator.executions.values()
        )

    @property
    def moving_offset(self) -> int | None:
        """Return the offset between the targeted position and the current one if the cover is moving."""

        is_moving = self.device.states.get(OverkizState.CORE_MOVING)
        current_closure = self.device.states.get(OverkizState.CORE_CLOSURE)
        target_closure = self.device.states.get(OverkizState.CORE_TARGET_CLOSURE)

        if not is_moving or not current_closure or not target_closure:
            return None

        return cast(int, current_closure.value) - cast(int, target_closure.value)
