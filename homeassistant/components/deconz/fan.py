"""Support for deCONZ fans."""
from __future__ import annotations

from homeassistant.components.fan import (
    DOMAIN,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MEDIUM,
    SPEED_OFF,
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from .const import FANS, NEW_LIGHT
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry

ORDERED_NAMED_FAN_SPEEDS = [1, 2, 3, 4]

LEGACY_SPEED_TO_DECONZ = {SPEED_OFF: 0, SPEED_LOW: 1, SPEED_MEDIUM: 2, SPEED_HIGH: 4}
LEGACY_DECONZ_TO_SPEED = {0: SPEED_OFF, 1: SPEED_LOW, 2: SPEED_MEDIUM, 4: SPEED_HIGH}


async def async_setup_entry(hass, config_entry, async_add_entities) -> None:
    """Set up fans for deCONZ component."""
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_fan(lights=gateway.api.lights.values()) -> None:
        """Add fan from deCONZ."""
        entities = []

        for light in lights:

            if light.type in FANS and light.uniqueid not in gateway.entities[DOMAIN]:
                entities.append(DeconzFan(light, gateway))

        if entities:
            async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, gateway.async_signal_new_device(NEW_LIGHT), async_add_fan
        )
    )

    async_add_fan()


class DeconzFan(DeconzDevice, FanEntity):
    """Representation of a deCONZ fan."""

    TYPE = DOMAIN

    def __init__(self, device, gateway) -> None:
        """Set up fan."""
        super().__init__(device, gateway)

        self._default_on_speed = 2
        if self._device.speed in ORDERED_NAMED_FAN_SPEEDS:
            self._default_on_speed = self._device.speed

        self._attr_supported_features = SUPPORT_SET_SPEED

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        return self._device.speed != 0

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self._device.speed == 0:
            return 0
        if self._device.speed not in ORDERED_NAMED_FAN_SPEEDS:
            return None
        return ordered_list_item_to_percentage(
            ORDERED_NAMED_FAN_SPEEDS, self._device.speed
        )

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return len(ORDERED_NAMED_FAN_SPEEDS)

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds.

        Legacy fan support.
        """
        return list(LEGACY_SPEED_TO_DECONZ)

    def speed_to_percentage(self, speed: str) -> int:
        """Convert speed to percentage.

        Legacy fan support.
        """
        if speed == SPEED_OFF:
            return 0

        if speed not in LEGACY_SPEED_TO_DECONZ:
            speed = SPEED_MEDIUM

        return ordered_list_item_to_percentage(
            ORDERED_NAMED_FAN_SPEEDS, LEGACY_SPEED_TO_DECONZ[speed]
        )

    def percentage_to_speed(self, percentage: int) -> str:
        """Convert percentage to speed.

        Legacy fan support.
        """
        if percentage == 0:
            return SPEED_OFF
        return LEGACY_DECONZ_TO_SPEED.get(
            percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage),
            SPEED_MEDIUM,
        )

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._attr_supported_features

    @callback
    def async_update_callback(self, force_update=False) -> None:
        """Store latest configured speed from the device."""
        if self._device.speed in ORDERED_NAMED_FAN_SPEEDS:
            self._default_on_speed = self._device.speed
        super().async_update_callback(force_update)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        await self._device.set_speed(
            percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
        )

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan.

        Legacy fan support.
        """
        if speed not in LEGACY_SPEED_TO_DECONZ:
            raise ValueError(f"Unsupported speed {speed}")

        await self._device.set_speed(LEGACY_SPEED_TO_DECONZ[speed])

    async def async_turn_on(
        self,
        speed: str = None,
        percentage: int = None,
        preset_mode: str = None,
        **kwargs,
    ) -> None:
        """Turn on fan."""
        new_speed = self._default_on_speed

        if percentage is not None:
            new_speed = percentage_to_ordered_list_item(
                ORDERED_NAMED_FAN_SPEEDS, percentage
            )

        await self._device.set_speed(new_speed)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off fan."""
        await self._device.set_speed(0)
