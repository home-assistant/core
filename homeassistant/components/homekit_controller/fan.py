"""Support for Homekit fans."""
import logging

from homekit.model.characteristics import CharacteristicsTypes

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_DIRECTION,
    SUPPORT_OSCILLATE,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.core import callback

from . import KNOWN_DEVICES, HomeKitEntity

_LOGGER = logging.getLogger(__name__)

# 0 is clockwise, 1 is counter-clockwise. The match to forward and reverse is so that
# its consistent with homeassistant.components.homekit.
DIRECTION_TO_HK = {
    DIRECTION_REVERSE: 1,
    DIRECTION_FORWARD: 0,
}
HK_DIRECTION_TO_HA = {v: k for (k, v) in DIRECTION_TO_HK.items()}

SPEED_TO_PCNT = {
    SPEED_HIGH: 100,
    SPEED_MEDIUM: 50,
    SPEED_LOW: 25,
    SPEED_OFF: 0,
}


class BaseHomeKitFan(HomeKitEntity, FanEntity):
    """Representation of a Homekit fan."""

    # This must be set in subclasses to the name of a boolean characteristic
    # that controls whether the fan is on or off.
    on_characteristic = None

    def __init__(self, *args):
        """Initialise the fan."""
        self._on = None
        self._features = 0
        self._rotation_direction = 0
        self._rotation_speed = 0
        self._swing_mode = 0

        super().__init__(*args)

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.SWING_MODE,
            CharacteristicsTypes.ROTATION_DIRECTION,
            CharacteristicsTypes.ROTATION_SPEED,
        ]

    def _setup_rotation_direction(self, char):
        self._features |= SUPPORT_DIRECTION

    def _setup_rotation_speed(self, char):
        self._features |= SUPPORT_SET_SPEED

    def _setup_swing_mode(self, char):
        self._features |= SUPPORT_OSCILLATE

    def _update_rotation_direction(self, value):
        self._rotation_direction = value

    def _update_rotation_speed(self, value):
        self._rotation_speed = value

    def _update_swing_mode(self, value):
        self._swing_mode = value

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._on

    @property
    def speed(self):
        """Return the current speed."""
        if not self.is_on:
            return SPEED_OFF
        if self._rotation_speed > SPEED_TO_PCNT[SPEED_MEDIUM]:
            return SPEED_HIGH
        if self._rotation_speed > SPEED_TO_PCNT[SPEED_LOW]:
            return SPEED_MEDIUM
        if self._rotation_speed > SPEED_TO_PCNT[SPEED_OFF]:
            return SPEED_LOW
        return SPEED_OFF

    @property
    def speed_list(self):
        """Get the list of available speeds."""
        if self.supported_features & SUPPORT_SET_SPEED:
            return [SPEED_OFF, SPEED_LOW, SPEED_MEDIUM, SPEED_HIGH]
        return []

    @property
    def current_direction(self):
        """Return the current direction of the fan."""
        return HK_DIRECTION_TO_HA[self._rotation_direction]

    @property
    def oscillating(self):
        """Return whether or not the fan is currently oscillating."""
        return self._swing_mode == 1

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._features

    async def async_set_direction(self, direction):
        """Set the direction of the fan."""
        await self._accessory.put_characteristics(
            [
                {
                    "aid": self._aid,
                    "iid": self._chars["rotation.direction"],
                    "value": DIRECTION_TO_HK[direction],
                }
            ]
        )

    async def async_set_speed(self, speed):
        """Set the speed of the fan."""
        if speed == SPEED_OFF:
            return await self.async_turn_off()

        await self._accessory.put_characteristics(
            [
                {
                    "aid": self._aid,
                    "iid": self._chars["rotation.speed"],
                    "value": SPEED_TO_PCNT[speed],
                }
            ]
        )

    async def async_oscillate(self, oscillating: bool):
        """Oscillate the fan."""
        await self._accessory.put_characteristics(
            [
                {
                    "aid": self._aid,
                    "iid": self._chars["swing-mode"],
                    "value": 1 if oscillating else 0,
                }
            ]
        )

    async def async_turn_on(self, speed=None, **kwargs):
        """Turn the specified fan on."""

        characteristics = []

        if not self.is_on:
            characteristics.append(
                {
                    "aid": self._aid,
                    "iid": self._chars[self.on_characteristic],
                    "value": True,
                }
            )

        if self.supported_features & SUPPORT_SET_SPEED and speed:
            characteristics.append(
                {
                    "aid": self._aid,
                    "iid": self._chars["rotation.speed"],
                    "value": SPEED_TO_PCNT[speed],
                },
            )

        if not characteristics:
            return

        await self._accessory.put_characteristics(characteristics)

    async def async_turn_off(self, **kwargs):
        """Turn the specified fan off."""
        characteristics = [
            {
                "aid": self._aid,
                "iid": self._chars[self.on_characteristic],
                "value": False,
            }
        ]
        await self._accessory.put_characteristics(characteristics)


class HomeKitFanV1(BaseHomeKitFan):
    """Implement fan support for public.hap.service.fan."""

    on_characteristic = "on"

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [CharacteristicsTypes.ON] + super().get_characteristic_types()

    def _update_on(self, value):
        self._on = value == 1


class HomeKitFanV2(BaseHomeKitFan):
    """Implement fan support for public.hap.service.fanv2."""

    on_characteristic = "active"

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity cares about."""
        return [CharacteristicsTypes.ACTIVE] + super().get_characteristic_types()

    def _update_active(self, value):
        self._on = value == 1


ENTITY_TYPES = {
    "fan": HomeKitFanV1,
    "fanv2": HomeKitFanV2,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Homekit fans."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(aid, service):
        entity_class = ENTITY_TYPES.get(service["stype"])
        if not entity_class:
            return False
        info = {"aid": aid, "iid": service["iid"]}
        async_add_entities([entity_class(conn, info)], True)
        return True

    conn.add_listener(async_add_service)
