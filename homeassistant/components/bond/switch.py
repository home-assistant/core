"""Support for Bond generic devices."""
from typing import Any, Callable, List, Optional

from bond_api import Action, DeviceType

from homeassistant.components.switch import SwitchEntity
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
    """Set up Bond generic devices."""
    hub: BondHub = hass.data[DOMAIN][entry.entry_id]

    switches = [
        BondSwitch(hub, device)
        for device in hub.devices
        if DeviceType.is_generic(device.type)
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        await self._hub.bond.action(self._device.device_id, Action.turn_on())

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._hub.bond.action(self._device.device_id, Action.turn_off())

    async def async_update(self):
        """Fetch assumed state of the device from the hub using API."""
        state: dict = await self._hub.bond.device_state(self._device.device_id)
        self._power = state.get("power")
