"""Support for Homematic locks."""
from __future__ import annotations

from homeassistant.components.lock import SUPPORT_OPEN, LockEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_DISCOVER_DEVICES
from .entity import HMDevice


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Homematic lock platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        devices.append(HMLock(conf))

    add_entities(devices, True)


class HMLock(HMDevice, LockEntity):
    """Representation of a Homematic lock aka KeyMatic."""

    @property
    def is_locked(self):
        """Return true if the lock is locked."""
        return not bool(self._hm_get_state())

    def lock(self, **kwargs):
        """Lock the lock."""
        self._hmdevice.lock()

    def unlock(self, **kwargs):
        """Unlock the lock."""
        self._hmdevice.unlock()

    def open(self, **kwargs):
        """Open the door latch."""
        self._hmdevice.open()

    def _init_data_struct(self):
        """Generate the data dictionary (self._data) from metadata."""
        self._state = "STATE"
        self._data.update({self._state: None})

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_OPEN
