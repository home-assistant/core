"""Support for Fibaro locks."""
from __future__ import annotations

from typing import Any

from homeassistant.components.lock import DOMAIN, LockEntity, LockEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import FIBARO_DEVICES, FibaroDevice


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Fibaro locks."""
    if discovery_info is None:
        return

    entities: list[FibaroLock] = []
    for fibaro_device in hass.data[FIBARO_DEVICES]["lock"]:
        entity_description = LockEntityDescription(
            key="lock", name=fibaro_device.friendly_name
        )
        entities.append(FibaroLock(fibaro_device, entity_description))

    add_entities(entities, True)


class FibaroLock(FibaroDevice, LockEntity):
    """Representation of a Fibaro Lock."""

    def __init__(
        self, fibaro_device: Any, entity_description: LockEntityDescription
    ) -> None:
        """Initialize the Fibaro device."""
        super().__init__(fibaro_device)
        self.entity_description = entity_description
        self.entity_id = f"{DOMAIN}.{self.ha_id}"

    def lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        self.action("secure")
        self._attr_is_locked = True

    def unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        self.action("unsecure")
        self._attr_is_locked = False

    def update(self) -> None:
        """Update device state."""
        self._attr_is_locked = self.current_binary_state
