"""Support for Velux covers."""

from enum import StrEnum
from typing import Any, override

from pyvlx.const import Velocity
from pyvlx.opening_device import (
    Awning,
    Blind,
    DualRollerShutter,
    GarageDoor,
    Gate,
    OpeningDevice,
    Position,
    RollerShutter,
    Window,
)

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_SPEED,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityCapabilityAttribute,
    CoverEntityFeature,
    CoverSpeed,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VeluxConfigEntry
from .const import DOMAIN
from .entity import VeluxEntity, wrap_pyvlx_call_exceptions

PARALLEL_UPDATES = 1

_SPEED_TO_VELOCITY: dict[str, Velocity] = {
    CoverSpeed.SLOW: Velocity.SILENT,
    CoverSpeed.FAST: Velocity.FAST,
}

# Remove in 2027.6.0 together with their repair issues
_DEPRECATED_SPEED_TO_VELOCITY: dict[str, Velocity | None] = {
    "silent": Velocity.SILENT,
    "default": None,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VeluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up cover(s) for Velux platform."""
    pyvlx = config_entry.runtime_data.pyvlx

    entities: list[VeluxCover] = []
    for node in pyvlx.nodes:
        if isinstance(node, Blind):
            entities.append(VeluxBlind(hass, node, config_entry.entry_id))
        elif isinstance(node, DualRollerShutter):
            # add three entities, one for each part and the "dual" control
            entities.append(
                VeluxDualRollerShutter(
                    hass, node, config_entry.entry_id, VeluxDualRollerPart.DUAL
                )
            )
            entities.append(
                VeluxDualRollerShutter(
                    hass, node, config_entry.entry_id, VeluxDualRollerPart.UPPER
                )
            )
            entities.append(
                VeluxDualRollerShutter(
                    hass, node, config_entry.entry_id, VeluxDualRollerPart.LOWER
                )
            )
        elif isinstance(node, OpeningDevice):
            entities.append(VeluxCover(hass, node, config_entry.entry_id))

    async_add_entities(entities)


class VeluxCover(VeluxEntity, CoverEntity):
    """Representation of a Velux cover."""

    node: OpeningDevice
    _attr_translation_key = "cover"

    # Features common to all covers
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SPEED
    )
    # Remove the deprecated speeds in 2027.6.0, they are only listed so the
    # cover entity passes them on instead of dropping them.
    _attr_supported_speeds = [*_SPEED_TO_VELOCITY, *_DEPRECATED_SPEED_TO_VELOCITY]

    def __init__(
        self, hass: HomeAssistant, node: OpeningDevice, config_entry_id: str
    ) -> None:
        """Initialize VeluxCover."""
        super().__init__(hass, node, config_entry_id)
        match node:
            case Window():
                self._attr_device_class = CoverDeviceClass.WINDOW
            case Awning():
                self._attr_device_class = CoverDeviceClass.AWNING
            case GarageDoor():
                self._attr_device_class = CoverDeviceClass.GARAGE
            case Gate():
                self._attr_device_class = CoverDeviceClass.GATE
            case RollerShutter():
                self._attr_device_class = CoverDeviceClass.SHUTTER

    # Remove in 2027.6.0 when the deprecated speeds are removed
    @property
    @override
    def capability_attributes(self) -> dict[str, Any]:
        """Return capability attributes without the deprecated speeds."""
        return {
            CoverEntityCapabilityAttribute.SUPPORTED_SPEEDS: list(_SPEED_TO_VELOCITY)
        }

    def _velocity_from_speed(self, speed: str | None) -> Velocity | None:
        """Return pyvlx Velocity for the given speed string, or None for default."""
        if speed is None:
            return None
        if speed in _DEPRECATED_SPEED_TO_VELOCITY:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"deprecated_speed_{speed}",
                breaks_in_ha_version="2027.6.0",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=f"deprecated_speed_{speed}",
                translation_placeholders={"entity_id": self.entity_id},
            )
            return _DEPRECATED_SPEED_TO_VELOCITY[speed]
        # The cover entity validated the speed against _attr_supported_speeds.
        return _SPEED_TO_VELOCITY[speed]

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        if not self.node.position.known:
            return None
        # While the cover moves, pyvlx estimates the position from the
        # gateway's completion time and refreshes it every second.
        return 100 - self.node.get_position().position_percent

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if not self.node.position.known:
            return None
        return self.node.position.closed

    @property
    @override
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self.node.is_opening

    @property
    @override
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self.node.is_closing

    @wrap_pyvlx_call_exceptions
    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        velocity = self._velocity_from_speed(kwargs.get(ATTR_SPEED))
        await self.node.close(velocity=velocity, wait_for_completion=False)

    @wrap_pyvlx_call_exceptions
    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        velocity = self._velocity_from_speed(kwargs.get(ATTR_SPEED))
        await self.node.open(velocity=velocity, wait_for_completion=False)

    @wrap_pyvlx_call_exceptions
    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position_percent = 100 - kwargs[ATTR_POSITION]
        velocity = self._velocity_from_speed(kwargs.get(ATTR_SPEED))

        await self.node.set_position(
            Position(position_percent=position_percent),
            velocity=velocity,
            wait_for_completion=False,
        )

    @wrap_pyvlx_call_exceptions
    @override
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self.node.stop(wait_for_completion=False)


class VeluxDualRollerPart(StrEnum):
    """Enum for the parts of a dual roller shutter."""

    UPPER = "upper"
    LOWER = "lower"
    DUAL = "dual"


class VeluxDualRollerShutter(VeluxCover):
    """Representation of a Velux dual roller shutter cover."""

    node: DualRollerShutter
    _attr_device_class = CoverDeviceClass.SHUTTER

    def __init__(
        self,
        hass: HomeAssistant,
        node: DualRollerShutter,
        config_entry_id: str,
        part: VeluxDualRollerPart,
    ) -> None:
        """Initialize VeluxDualRollerShutter."""
        super().__init__(hass, node, config_entry_id)
        if part == VeluxDualRollerPart.DUAL:
            self._attr_name = None
        else:
            self._attr_unique_id = f"{self._attr_unique_id}_{part}"
            self._attr_translation_key = f"dual_roller_shutter_{part}"
        self.part = part

    @property
    def _part_position(self) -> Position:
        """Return the pyvlx Position for this part of the shutter."""
        if self.part == VeluxDualRollerPart.UPPER:
            return self.node.position_upper_curtain
        if self.part == VeluxDualRollerPart.LOWER:
            return self.node.position_lower_curtain
        return self.node.position

    @property
    @override
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        position = self._part_position
        if not position.known:
            return None
        return 100 - position.position_percent

    @property
    @override
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        position = self._part_position
        if not position.known:
            return None
        return position.closed

    @wrap_pyvlx_call_exceptions
    @override
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        velocity = self._velocity_from_speed(kwargs.get(ATTR_SPEED))
        await self.node.close(
            curtain=self.part, velocity=velocity, wait_for_completion=False
        )

    @wrap_pyvlx_call_exceptions
    @override
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        velocity = self._velocity_from_speed(kwargs.get(ATTR_SPEED))
        await self.node.open(
            curtain=self.part, velocity=velocity, wait_for_completion=False
        )

    @wrap_pyvlx_call_exceptions
    @override
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position_percent = 100 - kwargs[ATTR_POSITION]
        velocity = self._velocity_from_speed(kwargs.get(ATTR_SPEED))

        await self.node.set_position(
            Position(position_percent=position_percent),
            curtain=self.part,
            velocity=velocity,
            wait_for_completion=False,
        )


class VeluxBlind(VeluxCover):
    """Representation of a Velux blind cover."""

    node: Blind
    _attr_device_class = CoverDeviceClass.BLIND

    def __init__(self, hass: HomeAssistant, node: Blind, config_entry_id: str) -> None:
        """Initialize VeluxBlind."""
        super().__init__(hass, node, config_entry_id)

        self._attr_supported_features |= (
            CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.SET_TILT_POSITION
            | CoverEntityFeature.STOP_TILT
        )

    @property
    @override
    def current_cover_tilt_position(self) -> int | None:
        """Return the current tilt position of the cover."""
        if not self.node.orientation.known:
            return None
        return 100 - self.node.orientation.position_percent

    @wrap_pyvlx_call_exceptions
    @override
    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close cover tilt."""
        await self.node.close_orientation(wait_for_completion=False)

    @wrap_pyvlx_call_exceptions
    @override
    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open cover tilt."""
        await self.node.open_orientation(wait_for_completion=False)

    @wrap_pyvlx_call_exceptions
    @override
    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop cover tilt."""
        await self.node.stop_orientation(wait_for_completion=False)

    @wrap_pyvlx_call_exceptions
    @override
    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move cover tilt to a specific position."""
        position_percent = 100 - kwargs[ATTR_TILT_POSITION]
        orientation = Position(position_percent=position_percent)
        await self.node.set_orientation(
            orientation=orientation, wait_for_completion=False
        )
