"""Support for Homekit fans."""
from __future__ import annotations

from typing import Any

from aiohomekit.model.characteristics import CharacteristicsTypes
from aiohomekit.model.services import Service, ServicesTypes

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    FanEntity,
    FanEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from . import KNOWN_DEVICES, HomeKitEntity

# 0 is clockwise, 1 is counter-clockwise. The match to forward and reverse is so that
# its consistent with homeassistant.components.homekit.
DIRECTION_TO_HK = {
    DIRECTION_REVERSE: 1,
    DIRECTION_FORWARD: 0,
}
HK_DIRECTION_TO_HA = {v: k for (k, v) in DIRECTION_TO_HK.items()}


class BaseHomeKitFan(HomeKitEntity, FanEntity):
    """The base HomeKit Controller Fan Entity."""

    speed_read_characteristic: str
    speed_write_characteristic: str

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        chars = []

        if self.speed_read_characteristic:
            chars.append(self.speed_read_characteristic)

        if (
            self.speed_write_characteristic
            and self.speed_read_characteristic != self.speed_write_characteristic
        ):
            chars.append(self.speed_write_characteristic)

        return chars

    @property
    def _speed_range(self) -> tuple[int, int]:
        """Return the speed range."""
        return (self._min_speed, self._max_speed)

    @property
    def _min_speed(self) -> int:
        """Return the minimum speed."""
        return round(self.service[self.speed_read_characteristic].minValue or 0)

    @property
    def _max_speed(self) -> int:
        """Return the minimum speed."""
        return round(self.service[self.speed_read_characteristic].maxValue or 100)

    @property
    def speed_count(self) -> int:
        """Speed count for the fan."""
        return round(
            min(self._max_speed, 100)
            / max(1, self.service[self.speed_read_characteristic].minStep or 0)
        )

    @property
    def percentage(self) -> int:
        """Return the current speed percentage."""
        if not self.is_on:
            return 0

        return ranged_value_to_percentage(
            self._speed_range, self.service.value(self.speed_read_characteristic)
        )

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        features = 0

        if self.service.has(self.speed_read_characteristic):
            features |= FanEntityFeature.SET_SPEED

        return features


class HomeKitFan(BaseHomeKitFan):
    """Representation of a Homekit fan."""

    # This must be set in subclasses to the name of a boolean characteristic
    # that controls whether the fan is on or off.
    on_characteristic: str
    speed_read_characteristic = CharacteristicsTypes.ROTATION_SPEED
    speed_write_characteristic = CharacteristicsTypes.ROTATION_SPEED

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self.service.value(self.on_characteristic) == 1

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        return self.get_characteristic_types() + [
            self.on_characteristic,
            CharacteristicsTypes.SWING_MODE,
            CharacteristicsTypes.ROTATION_DIRECTION,
        ]

    @property
    def current_direction(self) -> str:
        """Return the current direction of the fan."""
        direction = self.service.value(CharacteristicsTypes.ROTATION_DIRECTION)
        return HK_DIRECTION_TO_HA[direction]

    @property
    def oscillating(self) -> bool:
        """Return whether or not the fan is currently oscillating."""
        oscillating = self.service.value(CharacteristicsTypes.SWING_MODE)
        return oscillating == 1

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        features = super().supported_features

        if self.service.has(CharacteristicsTypes.ROTATION_DIRECTION):
            features |= FanEntityFeature.DIRECTION

        if self.service.has(CharacteristicsTypes.SWING_MODE):
            features |= FanEntityFeature.OSCILLATE

        return features

    async def async_set_direction(self, direction: str) -> None:
        """Set the direction of the fan."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.ROTATION_DIRECTION: DIRECTION_TO_HK[direction]}
        )

    async def async_oscillate(self, oscillating: bool) -> None:
        """Oscillate the fan."""
        await self.async_put_characteristics(
            {CharacteristicsTypes.SWING_MODE: 1 if oscillating else 0}
        )

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan."""
        if percentage == 0:
            return await self.async_turn_off()

        await self.async_put_characteristics(
            {
                self.speed_write_characteristic: round(
                    percentage_to_ranged_value(self._speed_range, percentage)
                )
            }
        )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the specified fan on."""
        characteristics: dict[str, Any] = {}

        if not self.is_on:
            characteristics[self.on_characteristic] = True

        if (
            percentage is not None
            and self.supported_features & FanEntityFeature.SET_SPEED
        ):
            characteristics[self.speed_write_characteristic] = round(
                percentage_to_ranged_value(self._speed_range, percentage)
            )

        if characteristics:
            await self.async_put_characteristics(characteristics)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the specified fan off."""
        await self.async_put_characteristics({self.on_characteristic: False})


class HomeKitFanV1(HomeKitFan):
    """Implement fan support for public.hap.service.fan."""

    on_characteristic = CharacteristicsTypes.ON


class HomeKitFanV2(HomeKitFan):
    """Implement fan support for public.hap.service.fanv2."""

    on_characteristic = CharacteristicsTypes.ACTIVE


class EcobeeFan(BaseHomeKitFan):
    """Implement fan support for ecobee fans."""

    speed_read_characteristic = CharacteristicsTypes.VENDOR_ECOBEE_FAN_READ_SPEED
    speed_write_characteristic = CharacteristicsTypes.VENDOR_ECOBEE_FAN_WRITE_SPEED
    default_percentage = 50

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return bool(self.percentage)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan."""
        # Sending the fan mode request sometimes ends up getting ignored by ecobee
        # and this might be because it the older value instead of newer, and ecobee
        # thinks there is nothing to do.
        # So in order to make sure that the request is executed by ecobee, we need
        # to send a different value before sending the target value.
        # Fan mode value is a value from 0 to 100. We send a value off by 1 first.
        value = ranged_value_to_percentage(self._speed_range, percentage)
        if value > self._min_speed:
            other_value = value - 1
        else:
            other_value = self._min_speed + 1

        if value != other_value:
            await self.async_put_characteristics(
                {self.speed_write_characteristic: other_value}
            )
        await self.async_put_characteristics({self.speed_write_characteristic: value})

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the specified fan on."""
        await self.async_set_percentage(percentage or self.default_percentage)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the specified fan off."""
        await self.async_set_percentage(0)


ENTITY_TYPES = {
    ServicesTypes.FAN: HomeKitFanV1,
    ServicesTypes.FAN_V2: HomeKitFanV2,
}

FAN_ENTITY_CLASSES = {
    CharacteristicsTypes.VENDOR_ECOBEE_FAN_WRITE_SPEED: EcobeeFan,
}

FAN_ENTITY_CHARS = set(FAN_ENTITY_CLASSES)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit fans."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_service(service: Service) -> bool:
        entities: list[BaseHomeKitFan] = []
        info = {"aid": service.accessory.aid, "iid": service.iid}

        if entity_class := ENTITY_TYPES.get(service.type):
            entities.append(entity_class(conn, info))
        if not entity_class:
            for char in FAN_ENTITY_CHARS.intersection(service.characteristics_by_type):
                cls = FAN_ENTITY_CLASSES[char]
                entities.append(cls(conn, info))

        if not entities:
            return False

        async_add_entities(entities, True)
        return True

    conn.add_listener(async_add_service)
