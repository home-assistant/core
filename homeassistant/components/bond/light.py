"""Support for Bond lights."""
from typing import Any, Callable, List, Optional

from bond import DeviceTypes

from homeassistant.components.light import LightEntity
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
