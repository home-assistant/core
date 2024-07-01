"""Support for Overkiz covers - shutters etc."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from pyoverkiz.enums import (
    OverkizCommand,
    OverkizCommandParam,
    OverkizState,
    UIClass,
    UIWidget,
)
from pyoverkiz.models import Device

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityDescription,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HomeAssistantOverkizData
from .const import DOMAIN
from .coordinator import OverkizDataUpdateCoordinator
from .entity import OverkizDescriptiveEntity


def is_closed(device: Device) -> bool | None:
    """Return if the cover is closed."""

    if state := device.states[OverkizState.CORE_OPEN_CLOSED]:
        return state.value == OverkizCommandParam.CLOSED

    return False


@dataclass(frozen=True, kw_only=True)
class OverkizCoverDescription(CoverEntityDescription):
    """Class to describe an Overkiz cover."""

    open_command: OverkizCommand | None = None
    close_command: OverkizCommand | None = None
    stop_command: OverkizCommand | None = None
    current_position_state: OverkizState | None = None
    invert_position: bool = True
    set_position_command: OverkizCommand | None = None
    is_closed_fn: Callable[[Device], bool | None] | None = None
    current_tilt_position_state: OverkizState | None = None
    set_tilt_position_command: OverkizCommand | None = None
    open_tilt_command: OverkizCommand | None = None
    close_tilt_command: OverkizCommand | None = None
    stop_tilt_command: OverkizCommand | None = None


COVER_DESCRIPTIONS: list[OverkizCoverDescription] = [
    ## Overrides via UIWidget
    OverkizCoverDescription(
        key=UIWidget.PERGOLA_HORIZONTAL_AWNING_UNO,
        device_class=CoverDeviceClass.AWNING,
        current_position_state=OverkizState.CORE_DEPLOYMENT,
        set_position_command=OverkizCommand.SET_DEPLOYMENT,
        open_command=OverkizCommand.DEPLOY,
        close_command=OverkizCommand.UNDEPLOY,
        invert_position=False,
        is_closed_fn=is_closed,
        current_tilt_position_state=OverkizState.CORE_SLATE_ORIENTATION,
        set_tilt_position_command=OverkizCommand.SET_ORIENTATION,
        open_tilt_command=OverkizCommand.OPEN_SLATS,
        close_tilt_command=OverkizCommand.CLOSE_SLATS,
        stop_tilt_command=OverkizCommand.STOP,
    ),
    ## TiltOnlyVenetianBlind (UIWidget)
    ## Needs override to remove open/close commands
    # OverkizCoverDescription(
    #     key=UIWidget.TILT_ONLY_VENETIAN_BLIND,
    #     device_class=CoverDeviceClass.BLIND,
    #     is_closed_fn=is_closed,
    #     open_tilt_command=OverkizCommand.TILT_POSITIVE,
    #     close_tilt_command=OverkizCommand.TILT_NEGATIVE,
    #     stop_tilt_command=OverkizCommand.STOP,
    # ),
    ## Default cover behavior (via UIClass)
    OverkizCoverDescription(
        key=UIClass.AWNING,
        device_class=CoverDeviceClass.AWNING,
        current_position_state=OverkizState.CORE_DEPLOYMENT,
        set_position_command=OverkizCommand.SET_DEPLOYMENT,
        open_command=OverkizCommand.DEPLOY,
        close_command=OverkizCommand.UNDEPLOY,
        invert_position=False,
        is_closed_fn=is_closed,
        stop_command=OverkizCommand.STOP,
    ),
    OverkizCoverDescription(
        key=UIClass.ROLLER_SHUTTER,
        device_class=CoverDeviceClass.SHUTTER,
        current_position_state=OverkizState.CORE_CLOSURE,
        set_position_command=OverkizCommand.SET_CLOSURE,
        open_command=OverkizCommand.OPEN,
        close_command=OverkizCommand.CLOSE,
        is_closed_fn=is_closed,
        stop_command=OverkizCommand.STOP,
    ),
    OverkizCoverDescription(
        key=UIClass.ADJUSTABLE_SLATS_ROLLER_SHUTTER,
        device_class=CoverDeviceClass.BLIND,
        current_position_state=OverkizState.CORE_CLOSURE,
        set_position_command=OverkizCommand.SET_CLOSURE,
        open_command=OverkizCommand.OPEN,
        close_command=OverkizCommand.CLOSE,
        stop_command=OverkizCommand.STOP,
        current_tilt_position_state=OverkizState.CORE_SLATE_ORIENTATION,
        set_tilt_position_command=OverkizCommand.SET_ORIENTATION,
        stop_tilt_command=OverkizCommand.STOP,
    ),
    OverkizCoverDescription(
        key=UIClass.CURTAIN,
        device_class=CoverDeviceClass.CURTAIN,
        set_position_command=OverkizCommand.SET_CLOSURE,
        open_command=OverkizCommand.OPEN,
        close_command=OverkizCommand.CLOSE,
        stop_command=OverkizCommand.STOP,
    ),
    OverkizCoverDescription(
        key=UIClass.EXTERIOR_SCREEN,
        device_class=CoverDeviceClass.BLIND,
        current_position_state=OverkizState.CORE_CLOSURE,
        set_position_command=OverkizCommand.SET_CLOSURE,
        open_command=OverkizCommand.OPEN,
        close_command=OverkizCommand.CLOSE,
        is_closed_fn=is_closed,
        stop_command=OverkizCommand.STOP,
    ),
    OverkizCoverDescription(
        key=UIClass.EXTERIOR_VENETIAN_BLIND,
        device_class=CoverDeviceClass.BLIND,
        current_position_state=OverkizState.CORE_CLOSURE,
        set_position_command=OverkizCommand.SET_CLOSURE,
        open_command=OverkizCommand.OPEN,
        close_command=OverkizCommand.CLOSE,
        is_closed_fn=is_closed,
        stop_command=OverkizCommand.STOP,
        current_tilt_position_state=OverkizState.CORE_SLATE_ORIENTATION,
        set_tilt_position_command=OverkizCommand.SET_ORIENTATION,
        stop_tilt_command=OverkizCommand.STOP,
    ),
    OverkizCoverDescription(
        key=UIClass.PERGOLA,
        device_class=CoverDeviceClass.SHUTTER,
        is_closed_fn=is_closed,
        current_tilt_position_state=OverkizState.CORE_SLATE_ORIENTATION,
        set_tilt_position_command=OverkizCommand.SET_ORIENTATION,
        open_tilt_command=OverkizCommand.OPEN_SLATS,
        close_tilt_command=OverkizCommand.CLOSE_SLATS,
        stop_tilt_command=OverkizCommand.STOP,
    ),
    OverkizCoverDescription(
        key=UIClass.GARAGE_DOOR,
        device_class=CoverDeviceClass.GARAGE,
        open_command=OverkizCommand.OPEN,
        close_command=OverkizCommand.CLOSE,
        is_closed_fn=is_closed,
        stop_command=OverkizCommand.STOP,
    ),
    OverkizCoverDescription(
        key=UIClass.SCREEN,
        device_class=CoverDeviceClass.BLIND,
        current_position_state=OverkizState.CORE_CLOSURE,
        set_position_command=OverkizCommand.SET_CLOSURE,
        open_command=OverkizCommand.OPEN,
        close_command=OverkizCommand.CLOSE,
        is_closed_fn=is_closed,
        stop_command=OverkizCommand.STOP,
    ),
    OverkizCoverDescription(
        key=UIClass.SHUTTER,
        device_class=CoverDeviceClass.SHUTTER,
        current_position_state=OverkizState.CORE_CLOSURE,
        set_position_command=OverkizCommand.SET_CLOSURE,
        open_command=OverkizCommand.OPEN,
        close_command=OverkizCommand.CLOSE,
        is_closed_fn=is_closed,
        stop_command=OverkizCommand.STOP,
    ),
    OverkizCoverDescription(
        key=UIClass.SWINGING_SHUTTER,
        device_class=CoverDeviceClass.SHUTTER,
        current_position_state=OverkizState.CORE_CLOSURE,
        set_position_command=OverkizCommand.SET_CLOSURE,
        open_command=OverkizCommand.OPEN,
        close_command=OverkizCommand.CLOSE,
        is_closed_fn=is_closed,
        stop_command=OverkizCommand.STOP,
    ),
    OverkizCoverDescription(
        key=UIClass.VENETIAN_BLIND,
        device_class=CoverDeviceClass.BLIND,
        open_command=OverkizCommand.OPEN,
        close_command=OverkizCommand.CLOSE,
        is_closed_fn=is_closed,
        open_tilt_command=OverkizCommand.TILT_UP,
        close_tilt_command=OverkizCommand.TILT_DOWN,
        stop_tilt_command=OverkizCommand.STOP,
    ),
]

SUPPORTED_DEVICES = {description.key: description for description in COVER_DESCRIPTIONS}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Overkiz covers from a config entry."""
    data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]

    entities = [
        OverkizCover(
            device.device_url,
            data.coordinator,
            description,
        )
        for device in data.platforms[Platform.COVER]
        if (
            description := SUPPORTED_DEVICES.get(device.widget)
            or SUPPORTED_DEVICES.get(device.ui_class)
        )
    ]

    # Cover platform does not support configuring the speed of the cover
    # For covers where the speed can be configured, we create a separate entity
    entities += [
        OverkizLowSpeedCover(device.device_url, data.coordinator, description)
        for device in data.platforms[Platform.COVER]
        if (
            description := SUPPORTED_DEVICES.get(device.widget)
            or SUPPORTED_DEVICES.get(device.ui_class)
        )
        and OverkizCommand.SET_CLOSURE_AND_LINEAR_SPEED in device.definition.commands
    ]

    async_add_entities(entities)


class OverkizCover(OverkizDescriptiveEntity, CoverEntity):
    """Representation of an Overkiz Cover."""

    entity_description: OverkizCoverDescription

    def __init__(
        self,
        device_url: str,
        coordinator: OverkizDataUpdateCoordinator,
        description: OverkizCoverDescription,
    ) -> None:
        """Initialize the device."""
        super().__init__(device_url, coordinator, description)

        # Use device url as unique ID for backwards compatibility
        self._attr_unique_id = self.device.device_url

        # Overkiz does support covers where only tilt commands are supported
        # and HA sets by default open/close as supported feature which conflicts
        supported_features = CoverEntityFeature(0)

        if self.entity_description.open_command and self.executor.has_command(
            self.entity_description.open_command
        ):
            supported_features |= CoverEntityFeature.OPEN

            if self.entity_description.stop_command and self.executor.has_command(
                self.entity_description.stop_command
            ):
                supported_features |= CoverEntityFeature.STOP

        if self.entity_description.close_command and self.executor.has_command(
            self.entity_description.close_command
        ):
            supported_features |= CoverEntityFeature.CLOSE

        if self.entity_description.open_tilt_command and self.executor.has_command(
            self.entity_description.open_tilt_command
        ):
            supported_features |= CoverEntityFeature.OPEN_TILT

            if self.entity_description.stop_tilt_command and self.executor.has_command(
                self.entity_description.stop_tilt_command
            ):
                supported_features |= CoverEntityFeature.STOP_TILT

        if self.entity_description.close_tilt_command and self.executor.has_command(
            self.entity_description.close_tilt_command
        ):
            supported_features |= CoverEntityFeature.CLOSE_TILT

        if (
            self.entity_description.set_tilt_position_command
            and self.executor.has_command(
                self.entity_description.set_tilt_position_command
            )
        ):
            supported_features |= CoverEntityFeature.SET_TILT_POSITION

        if self.entity_description.set_position_command and self.executor.has_command(
            self.entity_description.set_position_command
        ):
            supported_features |= CoverEntityFeature.SET_POSITION

        self._attr_supported_features = supported_features

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if is_closed_fn := self.entity_description.is_closed_fn:
            return is_closed_fn(self.device)

        return None

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        state_name = self.entity_description.current_position_state

        if (
            state_name
            and (state := self.device.states[state_name])
            and (position := state.value_as_int)
        ):
            if self.entity_description.invert_position:
                position = 100 - position

            return position

        return None

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
        state_name = self.entity_description.current_tilt_position_state

        if (
            state_name
            and (state := self.device.states[state_name])
            and (position := state.value_as_int)
        ):
            if self.entity_description.invert_position:
                position = 100 - position

            return position

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
        current_closure = self.device.states.get(OverkizState.CORE_CLOSURE)
        target_closure = self.device.states.get(OverkizState.CORE_TARGET_CLOSURE)

        if not current_closure or not target_closure:
            return None

        return cast(int, current_closure.value) - cast(int, target_closure.value)


class OverkizLowSpeedCover(OverkizCover):
    """Representation of an Overkiz Low Speed cover."""

    entity_description: OverkizCoverDescription

    def __init__(
        self,
        device_url: str,
        coordinator: OverkizDataUpdateCoordinator,
        description: OverkizCoverDescription,
    ) -> None:
        """Initialize the device."""
        super().__init__(device_url, coordinator, description)

        self._attr_name = "Low speed"
        self._attr_unique_id = f"{self._attr_unique_id}_low_speed"

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        await self.async_set_cover_position_low_speed(**kwargs)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.async_set_cover_position_low_speed(**{ATTR_POSITION: 100})

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.async_set_cover_position_low_speed(**{ATTR_POSITION: 0})

    async def async_set_cover_position_low_speed(self, **kwargs: Any) -> None:
        """Move the cover to a specific position with a low speed."""
        position = 100 - kwargs.get(ATTR_POSITION, 0)

        await self.executor.async_execute_command(
            OverkizCommand.SET_CLOSURE_AND_LINEAR_SPEED,
            position,
            OverkizCommandParam.LOWSPEED,
        )
