"""Support for Bond generic devices."""
from typing import Any, Callable, List, Optional

from bond import DeviceTypes

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from ..switch import SwitchEntity
from .const import DOMAIN
from .entity import BondEntity
from .utils import BondDevice, BondHub


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up Bond generic devices."""
    hub: BondHub = hass.data[DOMAIN][entry.entry_id]

    devices = await hass.async_add_executor_job(hub.get_bond_devices)

    switches = [
        BondSwitch(hub, device)
        for device in devices
        if device.type == DeviceTypes.GENERIC_DEVICE
    ]

    async_add_entities(switches, True)


class BondSwitch(BondEntity, SwitchEntity):
    """Representation of a Bond generic device."""

    def __init__(self, hub: BondHub, device: BondDevice):
        """Create HA entity representing Bond generic device (switch)."""
        super().__init__(hub, device)

        self._power: Optional[bool] = None

    @property
    def is_on(self) -> bool:
        """Return True if power is on."""
        return self._power == 1

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self._hub.bond.turnOn(self._device.device_id)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self._hub.bond.turnOff(self._device.device_id)

    def update(self):
        """Fetch assumed state of the device from the hub using API."""
        state: dict = self._hub.bond.getDeviceState(self._device.device_id)
        self._power = state.get("power")
