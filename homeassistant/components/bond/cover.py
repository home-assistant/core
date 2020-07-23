"""Support for Bond covers."""
from typing import Any, Callable, List, Optional

from bond_api import Action, DeviceType

from homeassistant.components.cover import DEVICE_CLASS_SHADE, CoverEntity
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
    """Set up Bond cover devices."""
    hub: BondHub = hass.data[DOMAIN][entry.entry_id]

    covers = [
        BondCover(hub, device)
        for device in hub.devices
        if device.type == DeviceType.MOTORIZED_SHADES
    ]

    async_add_entities(covers, True)


class BondCover(BondEntity, CoverEntity):
    """Representation of a Bond cover."""

    def __init__(self, hub: BondHub, device: BondDevice):
        """Create HA entity representing Bond cover."""
        super().__init__(hub, device)

        self._closed: Optional[bool] = None

    @property
    def device_class(self) -> Optional[str]:
        """Get device class."""
        return DEVICE_CLASS_SHADE

    async def async_update(self):
        """Fetch assumed state of the cover from the hub using API."""
        state: dict = await self._hub.bond.device_state(self._device.device_id)
        cover_open = state.get("open")
        self._closed = True if cover_open == 0 else False if cover_open == 1 else None

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return self._closed

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._hub.bond.action(self._device.device_id, Action.open())

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self._hub.bond.action(self._device.device_id, Action.close())

    async def async_stop_cover(self, **kwargs):
        """Hold cover."""
        await self._hub.bond.action(self._device.device_id, Action.hold())
