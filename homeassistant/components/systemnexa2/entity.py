"""Base entity for SystemNexa2 integration."""

from sn2.device import Device

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity


class SystemNexa2Entity(Entity):
    """Base entity class for SystemNexa2 devices."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        device: Device,
        entry_id: str,
        unique_entity_id: str,
        name: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the SystemNexa2 entity."""
        self._device = device
        self._attr_name = name
        self._attr_unique_id = f"{entry_id}-{unique_entity_id}"
        self._attr_device_info = device_info
