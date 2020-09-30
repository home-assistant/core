"""Support for deCONZ switches."""
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

from .const import FANS, NEW_LIGHT
from .deconz_device import DeconzDevice
from .gateway import get_gateway_from_config_entry

SPEEDS = {SPEED_OFF: 0, SPEED_LOW: 1, SPEED_MEDIUM: 2, SPEED_HIGH: 4}


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up deCONZ platforms."""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up fans for deCONZ component.

    Fans are based on the same device class as lights in deCONZ.
    """
    gateway = get_gateway_from_config_entry(hass, config_entry)
    gateway.entities[DOMAIN] = set()

    @callback
    def async_add_fan(lights):
        """Add fan from deCONZ."""
        entities = []

        for light in lights:

            if light.type in FANS and light.uniqueid not in gateway.entities[DOMAIN]:
                entities.append(DeconzFan(light, gateway))

        async_add_entities(entities, True)

    gateway.listeners.append(
        async_dispatcher_connect(
            hass, gateway.async_signal_new_device(NEW_LIGHT), async_add_fan
        )
    )

    async_add_fan(gateway.api.lights.values())


class DeconzFan(DeconzDevice, FanEntity):
    """Representation of a deCONZ fan."""

    TYPE = DOMAIN

    def __init__(self, device, gateway) -> None:
        """Set up fan."""
        super().__init__(device, gateway)

        self._features = SUPPORT_SET_SPEED

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        return self._device.speed != SPEEDS[SPEED_OFF]

    @property
    def speed(self) -> int:
        """Return the current speed."""
        return self._device.speed

    @property
    def speed_list(self) -> list:
        """Get the list of available speeds."""
        return list(SPEEDS.keys())

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._features

    async def async_set_speed(self, speed: str) -> None:
        """Set the speed of the fan."""
        data = {"speed": SPEEDS[speed]}
        await self._device.async_set_state(data)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on fan."""
        data = {"speed": SPEEDS[SPEED_MEDIUM]}
        await self._device.async_set_state(data)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off fan."""
        data = {"speed": SPEEDS[SPEED_OFF]}
        await self._device.async_set_state(data)
