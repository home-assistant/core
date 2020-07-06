"""Support for Bond covers."""
import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from bond import BOND_DEVICE_TYPE_MOTORIZED_SHADES, Bond

from homeassistant.components.cover import DEVICE_CLASS_SHADE, CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .utils import BondDevice, get_bond_devices

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity]], None],
) -> None:
    """Set up Bond cover devices."""

    bond: Bond = hass.data[DOMAIN][entry.entry_id]

    async def discover():
        devices = await get_bond_devices(hass, bond)
        covers = [
            BondCover(bond, device)
            for device in devices
            if device.type == BOND_DEVICE_TYPE_MOTORIZED_SHADES
        ]
        async_add_entities(covers)

    asyncio.create_task(discover())


class BondCover(CoverEntity):
    """Representation of a Bond cover."""

    def __init__(self, bond: Bond, device: BondDevice):
        """Create HA entity representing Bond cover."""
        self._bond = bond
        self._device = device

    @property
    def device_class(self) -> Optional[str]:
        """Get device class."""
        return DEVICE_CLASS_SHADE

    @property
    def unique_id(self) -> Optional[str]:
        """Get unique ID for the entity."""
        return self._device.device_id

    @property
    def name(self) -> Optional[str]:
        """Get entity name."""
        return self._device.name

    @property
    def device_info(self) -> Optional[Dict[str, Any]]:
        """Get a an HA device representing this cover."""
        return {ATTR_NAME: self.name, "identifiers": {(DOMAIN, self.unique_id)}}

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return None

    def open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._bond.open(self._device.device_id)

    def close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        self._bond.close(self._device.device_id)

    def stop_cover(self, **kwargs):
        """Hold cover."""
        self._bond.hold(self._device.device_id)
