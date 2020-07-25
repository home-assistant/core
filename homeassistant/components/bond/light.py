"""Support for Bond lights."""
from typing import Any, Callable, List, Optional

from bond import DeviceTypes

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

    devices = await hass.async_add_executor_job(hub.get_bond_devices)

    lights = [
        BondLight(hub, device)
        for device in devices
        if device.type == DeviceTypes.CEILING_FAN and device.supports_light()
    ]
    async_add_entities(lights, True)

    fireplaces = [
        BondFireplace(hub, device)
        for device in devices
        if device.type == DeviceTypes.FIREPLACE
    ]
    async_add_entities(fireplaces, True)


class BondLight(BondEntity, LightEntity):
    """Representation of a Bond light."""

    def __init__(self, hub: BondHub, device: BondDevice):
        """Create HA entity representing Bond fan."""
        super().__init__(hub, device)

        self._light: Optional[int] = None

    @property
    def is_on(self) -> bool:
        """Return if light is currently on."""
        return self._light == 1

    def update(self):
        """Fetch assumed state of the light from the hub using API."""
        state: dict = self._hub.bond.getDeviceState(self._device.device_id)
        self._light = state.get("light")

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        self._hub.bond.turnLightOn(self._device.device_id)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        self._hub.bond.turnLightOff(self._device.device_id)


class BondFireplace(BondEntity, LightEntity):
    """Representation of a Bond-controlled fireplace."""

    def __init__(self, hub: BondHub, device: BondDevice):
        """Create HA entity representing Bond fan."""
        super().__init__(hub, device)

        self._power: Optional[bool] = None
        # Bond flame level, 0-100
        self._flame: Optional[int] = None

    @property
    def supported_features(self) -> Optional[int]:
        """Flag brightness as supported feature to represent flame level."""
        return SUPPORT_BRIGHTNESS

    @property
    def is_on(self) -> bool:
        """Return True if power is on."""
        return self._power == 1

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the fireplace on."""
        self._hub.bond.turnOn(self._device.device_id)

        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness:
            flame = round((brightness * 100) / 255)
            self._hub.bond.setFlame(self._device.device_id, flame)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the fireplace off."""
        self._hub.bond.turnOff(self._device.device_id)

    @property
    def brightness(self):
        """Return the flame of this fireplace converted to HA brightness between 0..255."""
        return round(self._flame * 255 / 100) if self._flame else None

    @property
    def icon(self) -> Optional[str]:
        """Show fireplace icon for the entity."""
        return "mdi:fireplace" if self._power == 1 else "mdi:fireplace-off"

    def update(self):
        """Fetch assumed state of the device from the hub using API."""
        state: dict = self._hub.bond.getDeviceState(self._device.device_id)
        self._power = state.get("power")
        self._flame = state.get("flame")
