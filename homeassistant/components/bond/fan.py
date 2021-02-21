"""Support for Bond fans."""
import logging
import math
from typing import Any, Callable, List, Optional, Tuple

from bond_api import Action, BPUPSubscriptions, DeviceType, Direction

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    SUPPORT_DIRECTION,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.util.percentage import (
    int_states_in_range,
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .const import BPUP_SUBS, DOMAIN, HUB
from .entity import BondEntity
from .utils import BondDevice, BondHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up Bond fan devices."""
    data = hass.data[DOMAIN][entry.entry_id]
    hub: BondHub = data[HUB]
    bpup_subs: BPUPSubscriptions = data[BPUP_SUBS]

    fans = [
        BondFan(hub, device, bpup_subs)
        for device in hub.devices
        if DeviceType.is_fan(device.type)
    ]

    async_add_entities(fans, True)


class BondFan(BondEntity, FanEntity):
    """Representation of a Bond fan."""

    def __init__(self, hub: BondHub, device: BondDevice, bpup_subs: BPUPSubscriptions):
        """Create HA entity representing Bond fan."""
        super().__init__(hub, device, bpup_subs)

        self._power: Optional[bool] = None
        self._speed: Optional[int] = None
        self._direction: Optional[int] = None

    def _apply_state(self, state: dict):
        self._power = state.get("power")
        self._speed = state.get("speed")
        self._direction = state.get("direction")

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        features = 0
        if self._device.supports_speed():
            features |= SUPPORT_SET_SPEED
        if self._device.supports_direction():
            features |= SUPPORT_DIRECTION

        return features

    @property
    def _speed_range(self) -> Tuple[int, int]:
        """Return the range of speeds."""
        return (1, self._device.props.get("max_speed", 3))

    @property
    def percentage(self) -> Optional[str]:
        """Return the current speed percentage for the fan."""
        if not self._speed or not self._power:
            return 0
        return ranged_value_to_percentage(self._speed_range, self._speed)

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(self._speed_range)

    @property
    def current_direction(self) -> Optional[str]:
        """Return fan rotation direction."""
        direction = None
        if self._direction == Direction.FORWARD:
            direction = DIRECTION_FORWARD
        elif self._direction == Direction.REVERSE:
            direction = DIRECTION_REVERSE

        return direction

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the desired speed for the fan."""
        _LOGGER.debug("async_set_percentage called with percentage %s", percentage)

        if percentage == 0:
            await self.async_turn_off()
            return

        bond_speed = math.ceil(
            percentage_to_ranged_value(self._speed_range, percentage)
        )
        _LOGGER.debug(
            "async_set_percentage converted percentage %s to bond speed %s",
            percentage,
            bond_speed,
        )

        await self._hub.bond.action(
            self._device.device_id, Action.set_speed(bond_speed)
        )

    async def async_turn_on(
        self,
        speed: Optional[str] = None,
        percentage: Optional[int] = None,
        preset_mode: Optional[str] = None,
        **kwargs,
    ) -> None:
        """Turn on the fan."""
        _LOGGER.debug("Fan async_turn_on called with percentage %s", percentage)

        if percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            await self._hub.bond.action(self._device.device_id, Action.turn_on())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        await self._hub.bond.action(self._device.device_id, Action.turn_off())

    async def async_set_direction(self, direction: str):
        """Set fan rotation direction."""
        bond_direction = (
            Direction.REVERSE if direction == DIRECTION_REVERSE else Direction.FORWARD
        )
        await self._hub.bond.action(
            self._device.device_id, Action.set_direction(bond_direction)
        )
