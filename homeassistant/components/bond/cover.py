"""Support for Bond covers."""
from typing import Any, Callable, List, Optional

from bond import DeviceTypes

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

    devices = await hass.async_add_executor_job(hub.get_bond_devices)

    covers = [
        BondCover(hub, device)
        for device in devices
        if device.type == DeviceTypes.MOTORIZED_SHADES
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

    def update(self):
        """Fetch assumed state of the cover from the hub using API."""
        state: dict = self._hub.bond.getDeviceState(self._device.device_id)
        cover_open = state.get("open")
        self._closed = True if cover_open == 0 else False if cover_open == 1 else None

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return self._closed

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._hub.bond.open(self._device.device_id)

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        self._hub.bond.close(self._device.device_id)

    def stop_cover(self, **kwargs):
        """Hold cover."""
        self._hub.bond.hold(self._device.device_id)
