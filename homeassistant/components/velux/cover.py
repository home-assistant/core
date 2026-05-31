"""Support for Velux covers."""

from enum import StrEnum
from typing import Any

from pyvlx import Node
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
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import VeluxConfigEntry
from .entity import VeluxEntity, wrap_pyvlx_call_exceptions

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VeluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up cover(s) for Velux platform."""
    pyvlx = config_entry.runtime_data

    entities: list[VeluxCover] = []
    for node in pyvlx.nodes:
        if isinstance(node, Blind):
            entities.append(VeluxBlind(node, config_entry.entry_id))
        elif isinstance(node, DualRollerShutter):
            # add three entities, one for each part and the "dual" control
            entities.append(
                VeluxDualRollerShutter(
                    node, config_entry.entry_id, VeluxDualRollerPart.DUAL
                )
            )
            entities.append(
                VeluxDualRollerShutter(
                    node, config_entry.entry_id, VeluxDualRollerPart.UPPER
                )
            )
            entities.append(
                VeluxDualRollerShutter(
                    node, config_entry.entry_id, VeluxDualRollerPart.LOWER
                )
            )
        elif isinstance(node, OpeningDevice):
            entities.append(VeluxCover(node, config_entry.entry_id))

    async_add_entities(entities)


class VeluxCover(VeluxEntity, RestoreEntity, CoverEntity):
    """Representation of a Velux cover."""

    node: OpeningDevice

    # Features common to all covers
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.STOP
    )

    # Last position (HA percent: 0 = closed, 100 = open) carried across an
    # HA restart. The KLF200 reboot triggered by async_unload_entry leaves
    # the gateway reporting current_position = UNKNOWN for tens of seconds
    # up to several minutes after a restart, during which HA would otherwise
    # show every Velux cover as `unknown`. The cache is preferred over the
    # live pyvlx position only while node.position is not known.
    _restored_position_percent: int | None = None

    def __init__(self, node: OpeningDevice, config_entry_id: str) -> None:
        """Initialize VeluxCover."""
        super().__init__(node, config_entry_id)
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

    async def async_added_to_hass(self) -> None:
        """Register pyvlx callbacks and seed the restore-position cache.

        is_opening / is_closing are transient and not restored — pyvlx
        initialises them to False on every (re-)connect, which is the correct
        starting point after an HA restart. Only the position is brought back
        so the entity does not stay `unknown` until the first House
        Monitoring frame arrives.
        """
        await super().async_added_to_hass()
        live = self._live_position_percent()
        if live is not None:
            self._restored_position_percent = live
            return
        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        restored = last_state.attributes.get(ATTR_CURRENT_POSITION)
        # Accept the persisted attribute regardless of the persisted entity
        # state string: HA may have written state="unknown" during a previous
        # post-restart UNKNOWN window, but the current_position attribute is
        # often still a usable number.
        if isinstance(restored, (int, float)) and 0 <= restored <= 100:
            self._restored_position_percent = int(restored)

    @property
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        if self.node.position.known:
            return 100 - self.node.position.position_percent
        return self._restored_position_percent

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self.node.position.known:
            return self.node.position.closed
        if self._restored_position_percent is None:
            return None
        return self._restored_position_percent == 0

    def _live_position_percent(self) -> int | None:
        """Return the HA-percent position if pyvlx currently knows it.

        Overridden by VeluxDualRollerShutter so each part refreshes from its
        own pyvlx Position. Used by ``after_update_callback`` to keep the
        restore cache fresh — if pyvlx ever transitions a known node back to
        UNKNOWN (e.g. a fresh KLF200 reconnect mid-session), the fallback
        should reflect the most recent known live value, not the startup
        snapshot from ``async_get_last_state``.
        """
        if not self.node.position.known:
            return None
        return 100 - self.node.position.position_percent

    async def after_update_callback(self, node: Node) -> None:
        """Capture the latest known live position into the restore cache."""
        live = self._live_position_percent()
        if live is not None:
            self._restored_position_percent = live
        await super().after_update_callback(node)

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self.node.is_opening

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self.node.is_closing

    @wrap_pyvlx_call_exceptions
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.node.close(wait_for_completion=False)

    @wrap_pyvlx_call_exceptions
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.node.open(wait_for_completion=False)

    @wrap_pyvlx_call_exceptions
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position_percent = 100 - kwargs[ATTR_POSITION]

        await self.node.set_position(
            Position(position_percent=position_percent), wait_for_completion=False
        )

    @wrap_pyvlx_call_exceptions
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
        self, node: DualRollerShutter, config_entry_id: str, part: VeluxDualRollerPart
    ) -> None:
        """Initialize VeluxDualRollerShutter."""
        super().__init__(node, config_entry_id)
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
    def current_cover_position(self) -> int | None:
        """Return the current position of the cover."""
        position = self._part_position
        if position.known:
            return 100 - position.position_percent
        return self._restored_position_percent

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        position = self._part_position
        if position.known:
            return position.closed
        if self._restored_position_percent is None:
            return None
        return self._restored_position_percent == 0

    def _live_position_percent(self) -> int | None:
        """Return the HA-percent position of this part if pyvlx knows it.

        Used by the inherited ``after_update_callback`` so the restore cache
        is refreshed from the part-specific position rather than the
        device-level ``node.position``.
        """
        position = self._part_position
        if not position.known:
            return None
        return 100 - position.position_percent

    @wrap_pyvlx_call_exceptions
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self.node.close(curtain=self.part, wait_for_completion=False)

    @wrap_pyvlx_call_exceptions
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self.node.open(curtain=self.part, wait_for_completion=False)

    @wrap_pyvlx_call_exceptions
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position_percent = 100 - kwargs[ATTR_POSITION]

        await self.node.set_position(
            Position(position_percent=position_percent),
            curtain=self.part,
            wait_for_completion=False,
        )


class VeluxBlind(VeluxCover):
    """Representation of a Velux blind cover."""

    node: Blind
    _attr_device_class = CoverDeviceClass.BLIND

    def __init__(self, node: Blind, config_entry_id: str) -> None:
        """Initialize VeluxBlind."""
        super().__init__(node, config_entry_id)

        self._attr_supported_features |= (
            CoverEntityFeature.OPEN_TILT
            | CoverEntityFeature.CLOSE_TILT
            | CoverEntityFeature.SET_TILT_POSITION
            | CoverEntityFeature.STOP_TILT
        )

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return the current tilt position of the cover."""
        if not self.node.orientation.known:
            return None
        return 100 - self.node.orientation.position_percent

    @wrap_pyvlx_call_exceptions
    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close cover tilt."""
        await self.node.close_orientation(wait_for_completion=False)

    @wrap_pyvlx_call_exceptions
    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open cover tilt."""
        await self.node.open_orientation(wait_for_completion=False)

    @wrap_pyvlx_call_exceptions
    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop cover tilt."""
        await self.node.stop_orientation(wait_for_completion=False)

    @wrap_pyvlx_call_exceptions
    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move cover tilt to a specific position."""
        position_percent = 100 - kwargs[ATTR_TILT_POSITION]
        orientation = Position(position_percent=position_percent)
        await self.node.set_orientation(
            orientation=orientation, wait_for_completion=False
        )
