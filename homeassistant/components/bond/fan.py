"""Support for Bond fans."""
import math
from typing import Any, Callable, List, Optional

from bond import DeviceTypes, Directions

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_DIRECTION,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .entity import BondEntity
from .utils import BondDevice, BondHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up Bond fan devices."""
    hub: BondHub = hass.data[DOMAIN][entry.entry_id]

    devices = await hass.async_add_executor_job(hub.get_bond_devices)

    fans = [
        BondFan(hub, device)
        for device in devices
        if device.type == DeviceTypes.CEILING_FAN
    ]

    async_add_entities(fans, True)


class BondFan(BondEntity, FanEntity):
    """Representation of a Bond fan."""

    def __init__(self, hub: BondHub, device: BondDevice):
        """Create HA entity representing Bond fan."""
        super().__init__(hub, device)

        self._power: Optional[bool] = None
        self._speed: Optional[int] = None
        self._direction: Optional[int] = None

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
    def speed(self) -> Optional[str]:
        """Return the current speed."""
        if self._power == 0:
            return SPEED_OFF
        if not self._power or not self._speed:
            return None

        # map 1..max_speed Bond speed to 1..3 HA speed
        max_speed = self._device.props.get("max_speed", 3)
        ha_speed = math.ceil(self._speed * (len(self.speed_list) - 1) / max_speed)
        return self.speed_list[ha_speed]

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]

    @property
    def current_direction(self) -> Optional[str]:
        """Return fan rotation direction."""
        direction = None
        if self._direction == Directions.FORWARD:
            direction = DIRECTION_FORWARD
        elif self._direction == Directions.REVERSE:
            direction = DIRECTION_REVERSE

        return direction

    def update(self):
        """Fetch assumed state of the fan from the hub using API."""
        state: dict = self._hub.bond.getDeviceState(self._device.device_id)
        self._power = state.get("power")
        self._speed = state.get("speed")
        self._direction = state.get("direction")

    def set_speed(self, speed: str) -> None:
        """Set the desired speed for the fan."""
        max_speed = self._device.props.get("max_speed", 3)
        if speed == SPEED_LOW:
            bond_speed = 1
        elif speed == SPEED_HIGH:
            bond_speed = max_speed
        else:
            bond_speed = math.ceil(max_speed / 2)
        self._hub.bond.setSpeed(self._device.device_id, speed=bond_speed)

    def turn_on(self, speed: Optional[str] = None, **kwargs) -> None:
        """Turn on the fan."""
        if speed is not None:
            self.set_speed(speed)
        self._hub.bond.turnOn(self._device.device_id)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the fan off."""
        self._hub.bond.turnOff(self._device.device_id)

    def set_direction(self, direction: str) -> None:
        """Set fan rotation direction."""
        bond_direction = (
            Directions.REVERSE if direction == DIRECTION_REVERSE else Directions.FORWARD
        )
        self._hub.bond.setDirection(self._device.device_id, bond_direction)
