"""Support for Bond lights."""
from typing import Any, Callable, List, Optional

from bond_api import Action, DeviceType

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    SUPPORT_BRIGHTNESS,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from . import BondHub
from .const import DOMAIN
from .entity import BondEntity
from .utils import BondDevice


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up Bond light devices."""
    hub: BondHub = hass.data[DOMAIN][entry.entry_id]

    lights: List[Entity] = [
        BondLight(hub, device)
        for device in hub.devices
        if DeviceType.is_fan(device.type) and device.supports_light()
    ]

    fireplaces: List[Entity] = [
        BondFireplace(hub, device)
        for device in hub.devices
        if DeviceType.is_fireplace(device.type)
    ]

    async_add_entities(lights + fireplaces, True)


class BondLight(BondEntity, LightEntity):
    """Representation of a Bond light."""

    def __init__(self, hub: BondHub, device: BondDevice):
        """Create HA entity representing Bond fan."""
        super().__init__(hub, device)
        self._brightness: Optional[int] = None
        self._light: Optional[int] = None

    def _apply_state(self, state: dict):
        self._light = state.get("light")
        self._brightness = state.get("brightness")

    @property
    def supported_features(self) -> Optional[int]:
        """Flag supported features."""
        features = 0
        if self._device.supports_set_brightness():
            features |= SUPPORT_BRIGHTNESS

        return features

    @property
    def is_on(self) -> bool:
        """Return if light is currently on."""
        return self._light == 1

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 1..255."""
        brightness_value = (
            round(self._brightness * 255 / 100) if self._brightness else None
        )
        return brightness_value

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness:
            await self._hub.bond.action(
                self._device.device_id,
                Action.set_brightness(round((brightness * 100) / 255)),
            )
        else:
            await self._hub.bond.action(self._device.device_id, Action.turn_light_on())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self._hub.bond.action(self._device.device_id, Action.turn_light_off())


class BondFireplace(BondEntity, LightEntity):
    """Representation of a Bond-controlled fireplace."""

    def __init__(self, hub: BondHub, device: BondDevice):
        """Create HA entity representing Bond fan."""
        super().__init__(hub, device)

        self._power: Optional[bool] = None
        # Bond flame level, 0-100
        self._flame: Optional[int] = None

    def _apply_state(self, state: dict):
        self._power = state.get("power")
        self._flame = state.get("flame")

    @property
    def supported_features(self) -> Optional[int]:
        """Flag brightness as supported feature to represent flame level."""
        return SUPPORT_BRIGHTNESS

    @property
    def is_on(self) -> bool:
        """Return True if power is on."""
        return self._power == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the fireplace on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness:
            flame = round((brightness * 100) / 255)
            await self._hub.bond.action(self._device.device_id, Action.set_flame(flame))
        else:
            await self._hub.bond.action(self._device.device_id, Action.turn_on())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the fireplace off."""
        await self._hub.bond.action(self._device.device_id, Action.turn_off())

    @property
    def brightness(self):
        """Return the flame of this fireplace converted to HA brightness between 0..255."""
        return round(self._flame * 255 / 100) if self._flame else None

    @property
    def icon(self) -> Optional[str]:
        """Show fireplace icon for the entity."""
        return "mdi:fireplace" if self._power == 1 else "mdi:fireplace-off"
